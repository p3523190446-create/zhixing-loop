#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
# Target the camera's composite parent only. Never a hub, controller or CH32 board.
$targets = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_04B4&PID_00C3\\' })
if ($targets.Count -ne 1) { throw 'Expected one connected 04B4:00C3 camera parent; no device restarted.' }
$camera = $targets[0]
$evidence = Join-Path $PSScriptRoot '..\..\output\onboard_dashboard\camera-compat-20261026'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Write-Host ('Restarting camera only: ' + $camera.FriendlyName)
$reply = (& pnputil.exe /restart-device $camera.InstanceId 2>&1 | Out-String)
$reply | Set-Content -LiteralPath (Join-Path $evidence ('camera-restart-' + $stamp + '.log')) -Encoding UTF8
Write-Host $reply
if ($reply -match 'Access is denied|拒绝访问') { throw 'Windows denied the restart; no success recorded.' }
if ($reply -notmatch 'restarted successfully|成功重新启动|设备已重新启动') {
    Write-Host 'Restart result requires inspection; the exact command output has been saved.'
}
Write-Host 'No driver uninstall, firmware update, board command, hub restart or PC restart was requested.'
