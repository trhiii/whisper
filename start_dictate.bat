@echo off
chcp 65001 >nul
REM Start dictation service in the background

cd /d "%~dp0"

REM Check if already running
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq dictate.py*" 2>NUL | find /I "python.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo X Dictation is already running!
    echo    Run stop_dictate.bat to stop it first.
    exit /b 1
)

REM Activate venv and start in background
call .venv\Scripts\activate.bat
start /B pythonw dictate.py > dictate.log 2>&1

echo + Dictation started!
echo    Hold F9 to dictate
echo    Check logs: type dictate.log
echo    Stop with: stop_dictate.bat
