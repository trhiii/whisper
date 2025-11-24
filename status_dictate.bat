@echo off
chcp 65001 >nul
REM Check if dictation service is running

tasklist /FI "IMAGENAME eq pythonw.exe" 2>NUL | find /I "pythonw.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo + Dictation is running
    echo.
    tasklist /FI "IMAGENAME eq pythonw.exe"
    echo.
    echo Recent logs:
    powershell -Command "Get-Content dictate.log -Tail 5"
) else (
    echo X Dictation is not running
    echo    Start with: start_dictate.bat
)
