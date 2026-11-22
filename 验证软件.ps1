param([switch]$CompileOnly, [string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error 'Bundled Python was not found. Run tools/verify.py with an installed Python 3 interpreter.'
}
$verifyArgs = @('-X', 'utf8', (Join-Path $PSScriptRoot 'tools\verify.py'))
if ($CompileOnly) { $verifyArgs += '--compile-only' }
if ($Compiler) { $verifyArgs += @('--compiler', $Compiler) }
& $pythonPath @verifyArgs
exit $LASTEXITCODE
