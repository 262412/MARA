@echo off
setlocal
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
set "mara_exit=%ERRORLEVEL%"
if not "%MARA_REVIEWER_NONINTERACTIVE%"=="1" pause
exit /b %mara_exit%
