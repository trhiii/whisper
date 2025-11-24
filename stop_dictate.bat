@echo off
chcp 65001 >nul
REM Stop dictation service

REM Kill any python processes running dictate.py
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *dictate.py*" ^| find "python.exe"') do (
    taskkill /PID %%i /F >NUL 2>&1
)
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq pythonw.exe" ^| find "pythonw.exe"') do (
    taskkill /PID %%i /F >NUL 2>&1
)

echo + Dictation stopped!
