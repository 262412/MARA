@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\cli.ps1" %*
exit /b %ERRORLEVEL%
