param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$uiRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $uiRoot)
$uiPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $uiPython)) { throw '未找到本机 Python runtime。' }
$serviceFolder = Join-Path $projectRoot 'output\onboard_dashboard\pc-speed-20261021'
$runtimeFile = Join-Path $serviceFolder 'runtime.json'
New-Item -ItemType Directory -Path $serviceFolder -Force | Out-Null
$serviceConfig = $null
if (Test-Path -LiteralPath $runtimeFile) { $serviceConfig = Get-Content -LiteralPath $runtimeFile -Raw -Encoding UTF8 | ConvertFrom-Json }
$serviceBase = if ($serviceConfig -and $serviceConfig.base -match '^/[A-Za-z0-9_-]{24,64}$') { $serviceConfig.base } else { $null }
$alreadyRunning = $false
if ($serviceBase) {
  try { $info = Invoke-RestMethod -Uri ('http://127.0.0.1:8795'+$serviceBase+'/api/ui/info') -TimeoutSec 2; $alreadyRunning = $info.platform -eq 'PC' -and -not $info.demo } catch {}
}
if (-not $alreadyRunning) {
  $arguments = @('speed_server.py','--bind','0.0.0.0','--port','8795')
  if ($serviceBase) { $arguments += @('--base',$serviceBase) }
  $job = Start-Process -FilePath $uiPython -ArgumentList $arguments -WorkingDirectory $uiRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $serviceFolder 'startup-stdout.log') -RedirectStandardError (Join-Path $serviceFolder 'startup-stderr.log')
  $confirmed = $false
  for ($attempt=0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 150
    if ($job.HasExited) { throw ('服务启动失败，请查看 '+(Join-Path $serviceFolder 'startup-stderr.log')) }
    if (Test-Path -LiteralPath $runtimeFile) { $serviceConfig = Get-Content -LiteralPath $runtimeFile -Raw -Encoding UTF8 | ConvertFrom-Json; if ($serviceConfig.pid -eq $job.Id) { $confirmed=$true; break } }
  }
  if (-not $confirmed) { throw '调试服务启动尚未确认，请查看启动日志；勿重复打开串口。' }
}
$serviceConfig = Get-Content -LiteralPath $runtimeFile -Raw -Encoding UTF8 | ConvertFrom-Json
$url = 'http://127.0.0.1:8795'+$serviceConfig.base
$uiConfig = [ordered]@{pid=$serviceConfig.pid;bind=$serviceConfig.bind;port=8795;base=$serviceConfig.base;demo=$false;url=($url+'/desktop');desktop=($url+'/desktop');mobile=($url+'/mobile');transport='PC_P9';service_runtime=$runtimeFile}
$uiConfig | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $uiRoot 'runtime.json') -Encoding UTF8
Write-Host ('电脑调试台：'+$uiConfig.desktop)
Write-Host ('手机布局：'+$uiConfig.mobile)
Write-Host '四轮：按主控能力显示转向或麦轮横移。点击开启并按住方向才运动；启动入口不会启动车轮。'
Write-Host '服务会在后台保持运行；再次打开会复用，不会重复占用P9。'
if (-not $NoOpen) { Start-Process $uiConfig.desktop }

