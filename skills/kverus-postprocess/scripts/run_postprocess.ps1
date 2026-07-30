$ErrorActionPreference = 'Stop'

$base = if ($MyInvocation.UnboundArguments.Count -ge 1) { $MyInvocation.UnboundArguments[0] } else { if ($env:KVERUS_POSTPROCESS_BASE) { $env:KVERUS_POSTPROCESS_BASE } else { 'origin/main' } }

$scriptDir = $PSScriptRoot
$checker = Join-Path $scriptDir 'kverus_postprocess.py'
$simplifier = Join-Path $scriptDir '..\..\kverus-strip\scripts\simplify_proof.py'
$simplifier = [System.IO.Path]::GetFullPath($simplifier)

$ruleRepo       = $env:KVERUS_POSTPROCESS_RULE_REPO
$targetPaths    = $env:KVERUS_POSTPROCESS_TARGET_PATHS
$verifyCmd      = $env:KVERUS_POSTPROCESS_VERIFY_CMD
$formatCmd      = $env:KVERUS_POSTPROCESS_FORMAT_CMD
$includeSkills  = $env:KVERUS_POSTPROCESS_INCLUDE_SKILLS
$blockedPaths   = $env:KVERUS_POSTPROCESS_BLOCKED_PATHS
$generatedPaths = $env:KVERUS_POSTPROCESS_GENERATED_PATHS
$simplifyScope  = if ($env:KVERUS_POSTPROCESS_SIMPLIFY_SCOPE) { $env:KVERUS_POSTPROCESS_SIMPLIFY_SCOPE } else { 'modified' }
$skipSimplify   = $env:KVERUS_POSTPROCESS_SKIP_SIMPLIFY

function Invoke-Checker {
    $pyArgs = @($checker, '--base', $base, '--rule-repo', $ruleRepo)
    if ($targetPaths) {
        $pyArgs += '--target-path'
        $pyArgs += $targetPaths
    }
    if ($includeSkills -eq '1') {
        $pyArgs += '--include-skills'
    }
    if ($blockedPaths) {
        $pyArgs += '--blocked-path'
        $pyArgs += $blockedPaths
    }
    if ($generatedPaths) {
        $pyArgs += '--generated-path'
        $pyArgs += $generatedPaths
    }
    $pyArgs += '--refresh-rules'

    python3 @pyArgs
}

function Invoke-Simplifier {
    $pyArgs = @($simplifier, '--base', $base)
    if ($simplifyScope -ne 'all') {
        $pyArgs += '--modified-only'
    }
    if ($targetPaths) {
        $pyArgs += '--target-dir'
        $pyArgs += $targetPaths
    }
    if ($verifyCmd) {
        $pyArgs += '--verify-command'
        $pyArgs += $verifyCmd
        if ($formatCmd) {
            $pyArgs += '--format-command'
            $pyArgs += $formatCmd
        }
    } else {
        $pyArgs += '--dry-run'
    }

    python3 @pyArgs
}

Write-Host '== kverus-postprocess: refresh rules and check =='
Invoke-Checker
if (-not $?) { $firstStatus = $LASTEXITCODE } else { $firstStatus = 0 }

if ($verifyCmd) {
    Write-Host '== kverus-postprocess: verify =='
    cmd /c $verifyCmd
} else {
    Write-Host '== kverus-postprocess: verify skipped; set KVERUS_POSTPROCESS_VERIFY_CMD =='
}

Write-Host '== kverus-postprocess: simplify redundant asserts =='
if ($skipSimplify -eq '1') {
    Write-Host 'Skipping assert simplification because KVERUS_POSTPROCESS_SKIP_SIMPLIFY=1.'
} else {
    Invoke-Simplifier
    if (-not $verifyCmd) {
        Write-Host 'Assert simplification ran in dry-run mode; set KVERUS_POSTPROCESS_VERIFY_CMD to enable removals.'
    }
}

if ($verifyCmd) {
    Write-Host '== kverus-postprocess: verify after assert simplification =='
    cmd /c $verifyCmd
}

if ($formatCmd) {
    Write-Host '== kverus-postprocess: format =='
    cmd /c $formatCmd
} else {
    Write-Host '== kverus-postprocess: format skipped; set KVERUS_POSTPROCESS_FORMAT_CMD =='
}

Write-Host '== kverus-postprocess: final check =='
Invoke-Checker
if (-not $?) { $finalStatus = $LASTEXITCODE } else { $finalStatus = 0 }

Write-Host '== kverus-postprocess: git diff --check =='
git diff --check
if (-not $?) { $diffCheckStatus = $LASTEXITCODE } else { $diffCheckStatus = 0 }

Write-Host '== kverus-postprocess: git status =='
git status --short --branch

if ($firstStatus -ne 0) {
    Write-Host "Initial postprocess reported errors before final checks; final status was $finalStatus."
}

if ($finalStatus -ne 0) {
    exit $finalStatus
}
exit $diffCheckStatus
