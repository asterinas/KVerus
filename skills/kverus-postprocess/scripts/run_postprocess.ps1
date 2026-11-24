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
$enableSimplify = $env:KVERUS_POSTPROCESS_ENABLE_SIMPLIFY
$skipSimplify   = $env:KVERUS_POSTPROCESS_SKIP_SIMPLIFY
$refreshRules   = $env:KVERUS_POSTPROCESS_REFRESH_RULES

function Invoke-Checker([bool]$refresh) {
    $pyArgs = @($checker, '--base', $base)
    if ($ruleRepo) {
        $pyArgs += "--rule-repo=$ruleRepo"
    }
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
    if ($refresh) {
        $pyArgs += '--refresh-rules'
    } else {
        $pyArgs += '--no-refresh-rules'
    }

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
    } else {
        $pyArgs += '--dry-run'
    }

    python3 @pyArgs
}

$firstStatus = 0
if ($refreshRules -eq '1') {
    Write-Host '== kverus-postprocess: refresh rules and check =='
    Invoke-Checker $true
    $firstStatus = $LASTEXITCODE
}

if ($enableSimplify -eq '1' -and $skipSimplify -ne '1') {
    if ($verifyCmd) {
        Write-Host '== kverus-postprocess: verify before simplification =='
        cmd /c $verifyCmd
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Host '== kverus-postprocess: simplify redundant asserts =='
    Invoke-Simplifier
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not $verifyCmd) {
        Write-Host 'Assert simplification ran in dry-run mode; set KVERUS_POSTPROCESS_VERIFY_CMD to enable removals.'
    }
}

if ($formatCmd) {
    Write-Host '== kverus-postprocess: format =='
    cmd /c $formatCmd
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host '== kverus-postprocess: format skipped; set KVERUS_POSTPROCESS_FORMAT_CMD =='
}

if ($verifyCmd) {
    Write-Host '== kverus-postprocess: final verify =='
    cmd /c $verifyCmd
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host '== kverus-postprocess: verify skipped; set KVERUS_POSTPROCESS_VERIFY_CMD =='
}

Write-Host '== kverus-postprocess: final check =='
Invoke-Checker $false
$finalStatus = $LASTEXITCODE

Write-Host '== kverus-postprocess: git diff --check =='
git diff --check
$diffCheckStatus = $LASTEXITCODE

Write-Host '== kverus-postprocess: git status =='
git status --short --branch

if ($firstStatus -ne 0) {
    Write-Host "Initial postprocess reported errors before final checks; final status was $finalStatus."
}

if ($finalStatus -ne 0) {
    exit $finalStatus
}
exit $diffCheckStatus
