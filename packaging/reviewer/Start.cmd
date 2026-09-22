@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
set "mara_exit=%ERRORLEVEL%"
if not "%MARA_REVIEWER_NONINTERACTIVE%"=="1" pause
exit /b %mara_exit%
