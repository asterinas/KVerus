$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptDir
$SkillsSrc = Join-Path $RepoRoot 'skills'

$ScriptName = [System.IO.Path]::GetFileName($PSCommandPath)

function usage {
    Write-Host "Usage: $ScriptName [OPTIONS] <target-dir>"
    Write-Host ''
    Write-Host 'Install KVerus skills into a target project directory.'
    Write-Host ''
    Write-Host 'Arguments:'
    Write-Host '  target-dir    Path to the target project root (must exist)'
    Write-Host ''
    Write-Host 'Options:'
    Write-Host '  -m, --mode <symlink|copy>   Installation mode (default: symlink)'
    Write-Host '  -t, --targets <targets>     Comma-separated install targets: agent,claude (default: agent)'
    Write-Host '                            agent: .agents/skills (supports both Codex and OpenCode)'
    Write-Host '  -s, --skills <skills>       Comma-separated skill names to install (default: all)'
    Write-Host '  -f, --force                 Overwrite existing installations'
    Write-Host '  -h, --help                  Show this help'
    Write-Host ''
    Write-Host 'Examples:'
    Write-Host "  $ScriptName ~/my-project"
    Write-Host "  $ScriptName --mode copy --targets agent,claude ~/my-project"
    Write-Host "  $ScriptName --mode symlink --skills kverus-common,kverus-fix ~/my-project"
    exit 0
}

$mode = 'symlink'
$targets = 'agent'
$skills = ''
$force = $false
$targetDir = ''

$i = 0
while ($i -lt $args.Count) {
    $arg = $args[$i]
    switch ($arg) {
        '-m' { $mode = $args[++$i]; break }
        '--mode' { $mode = $args[++$i]; break }
        '-t' { $targets = $args[++$i]; break }
        '--targets' { $targets = $args[++$i]; break }
        '-s' { $skills = $args[++$i]; break }
        '--skills' { $skills = $args[++$i]; break }
        '-f' { $force = $true; break }
        '--force' { $force = $true; break }
        '-h' { usage; break }
        '--help' { usage; break }
        { $_ -like '-*' } {
            Write-Error "Error: unknown option $arg"
            exit 1
        }
        default {
            $targetDir = $arg
        }
    }
    $i++
}

if (-not $targetDir) {
    Write-Error 'Error: target directory is required'
    usage
}

if (-not (Test-Path $targetDir -PathType Container)) {
    Write-Error "Error: target directory does not exist: $targetDir"
    exit 1
}

if ($mode -ne 'symlink' -and $mode -ne 'copy') {
    Write-Error "Error: mode must be 'symlink' or 'copy'"
    exit 1
}

if (-not (Test-Path $SkillsSrc -PathType Container)) {
    Write-Error "Error: skills source directory not found: $SkillsSrc"
    exit 1
}

$targetDir = (Resolve-Path $targetDir).Path

# Collect skills to install
if ($skills) {
    $skillList = $skills -split ',' | ForEach-Object { $_.Trim() }
} else {
    $skillList = Get-ChildItem -Path $SkillsSrc -Directory | ForEach-Object { $_.Name }
}

# Validate all skills exist before installing
foreach ($skill in $skillList) {
    $skillPath = Join-Path $SkillsSrc $skill
    if (-not (Test-Path $skillPath -PathType Container)) {
        Write-Error "Error: skill not found: $skill"
        exit 1
    }
}

function Install-Skill {
    param(
        [string]$Skill,
        [string]$DestRoot
    )
    $dest = Join-Path $DestRoot $Skill
    $src = Join-Path $SkillsSrc $Skill

    if ((Test-Path $dest) -or (Test-Path $dest -PathType Leaf)) {
        if ($force) {
            Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
        } else {
            Write-Host "  SKIP $dest (already exists, use --force to overwrite)"
            return
        }
    }

    New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null

    if ($mode -eq 'symlink') {
        try {
            New-Item -ItemType SymbolicLink -Path $dest -Target $src -Force -ErrorAction Stop | Out-Null
            Write-Host "  LINK $dest -> $src"
        } catch {
            # SymbolicLink requires admin; try Junction (directory junction, no admin needed)
            try {
                New-Item -ItemType Junction -Path $dest -Target $src -Force -ErrorAction Stop | Out-Null
                Write-Host "  LINK (junction) $dest -> $src"
            } catch {
                Write-Warning "  Symlink/junction failed, falling back to copy for $Skill"
                Copy-Item -Recurse -Force -Path $src -Destination $dest
                Write-Host "  COPY $dest"
            }
        }
    } else {
        Copy-Item -Recurse -Force -Path $src -Destination $dest
        Write-Host "  COPY $dest"
    }
}

$targetList = $targets -split ',' | ForEach-Object { $_.Trim() }

Write-Host "Installing $($skillList.Count) skill(s) [mode=$mode]"
Write-Host ''

foreach ($target in $targetList) {
    switch ($target) {
        'agent' {
            $destRoot = Join-Path $targetDir '.agents\skills'
            Write-Host 'Target: .agents/skills/'
        }
        'claude' {
            $destRoot = Join-Path $targetDir '.claude\skills'
            Write-Host 'Target: .claude/skills/'
        }
        default {
            Write-Error "Error: unknown target '$target' (expected: agent, claude)"
            exit 1
        }
    }

    foreach ($skill in $skillList) {
        Install-Skill -Skill $skill -DestRoot $destRoot
    }

    $envFile = Join-Path (Split-Path $destRoot -Parent) 'kverus.env'
    $envContent = @"
# Auto-generated by install-skills.ps1. Points KVerus skills at the KVerus Python venv.
# Source in the shell running skill scripts:  . "`$AGENT_DIR/kverus.env"
export KVERUS_ROOT="$RepoRoot"
export KVERUS_PYTHON="`$KVERUS_ROOT/.venv/Scripts/python.exe"
"@
    Set-Content -Path $envFile -Value $envContent -Encoding utf8
    Write-Host "  ENV  $envFile (KVERUS_ROOT=$RepoRoot)"
    Write-Host ''
}

# Verify the KVerus venv can supply tree-sitter-verus to skill scripts.
$venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    Write-Host 'KVerus venv found.'
} else {
    Write-Warning "KVerus venv not found at $venvPy."
    Write-Warning 'Skill scripts will fall back to text-based parsing. Fix with:'
    Write-Warning "  cd `"$RepoRoot`"; uv sync"
}

Write-Host 'Done.'
