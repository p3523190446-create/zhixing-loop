@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" server.py
pause
