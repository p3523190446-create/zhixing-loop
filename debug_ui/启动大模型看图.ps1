param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$vlmUiRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$vlmProject = Split-Path -Parent (Split-Path -Parent $vlmUiRoot)
$vlmPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $vlmPython)) { throw '请先安装Python与Pillow，并用tools/start_large_vision.py启动。' }
& $vlmPython (Join-Path $vlmProject '知行回路软件\tools\start_large_vision.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw '模型服务没有正常启动，请检查large-vision运行日志。' }
$vlmRuntime = Get-Content -LiteralPath (Join-Path $vlmProject 'output\onboard_dashboard\large-vision-20261107\runtime.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host ('大模型专用页：'+$vlmRuntime.url)
Write-Host '电脑与小手机保持同一热点，Ollama保持运行。原车载页面可直接取图识别。'
if (-not $NoOpen) { Start-Process $vlmRuntime.url }
