$uiRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$uiPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $uiPython)) { Write-Host '未找到本机 Python runtime，请检查 README。'; exit 1 }
$uiListener = Get-NetTCPConnection -LocalPort 8772 -State Listen -ErrorAction SilentlyContinue
if ($uiListener) { Write-Host '8772端口已有服务，请先核对本目录runtime.json与实际服务，勿重复启动。'; exit 0 }
$uiJob = Start-Process -FilePath $uiPython -ArgumentList @('server.py','--bind','0.0.0.0','--port','8772') -WorkingDirectory $uiRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $uiRoot 'server-stdout.log') -RedirectStandardError (Join-Path $uiRoot 'server-stderr.log')
try {
  $uiRuntime = Join-Path $uiRoot 'runtime.json'
  for ($uiAttempt=0; $uiAttempt -lt 30; $uiAttempt++) {
    Start-Sleep -Milliseconds 100
    if ((Test-Path -LiteralPath $uiRuntime) -and ((Get-Content -LiteralPath $uiRuntime -Raw -Encoding UTF8 | ConvertFrom-Json).pid -eq $uiJob.Id)) { break }
    if ($uiJob.HasExited) { throw '调试台服务启动失败，查看server-stderr.log。' }
  }
  $uiConfig = Get-Content -LiteralPath $uiRuntime -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($uiConfig.pid -ne $uiJob.Id) { throw '服务启动未确认。' }
  Write-Host ('电脑：' + $uiConfig.desktop)
  Write-Host ('手机布局预览：' + $uiConfig.mobile)
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { Write-Host ('同局域网手机候选：http://' + $_.IPAddress + ':8772' + $uiConfig.base + '/mobile') }
  Write-Host '服务已启动，未自动开启任何实物动作。此窗口结束时关闭本次UI服务。'
  Read-Host '按回车结束UI服务'
} finally {
  if (-not $uiJob.HasExited) { Stop-Process -Id $uiJob.Id -ErrorAction SilentlyContinue }
}
