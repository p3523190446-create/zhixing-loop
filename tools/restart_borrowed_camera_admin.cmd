@echo off
echo This operation needs Run as administrator.
echo It targets only the connected 04B4:00C3 camera.
powershell.exe -NoProfile -File "%~dp0restart_borrowed_camera.ps1"
pause
