#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
# Restrict recovery to the original camera composite parent, never a hub/board.
$candidates = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_145F&PID_02EC\\' })
if ($candidates.Count -ne 1) { throw 'Expected exactly one original 145F:02EC camera parent; nothing restarted.' }
$evidence = Join-Path $PSScriptRoot '..\..\output\onboard_dashboard\algorithm-experiments-20261026'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$reply = (& pnputil.exe /restart-device $candidates[0].InstanceId 2>&1 | Out-String)
$reply | Set-Content -LiteralPath (Join-Path $evidence ('original-camera-restart-' + $stamp + '.log')) -Encoding UTF8
if ($reply -match 'Access is denied|拒绝访问') { throw 'Windows denied camera restart; no recovery confirmed.' }
