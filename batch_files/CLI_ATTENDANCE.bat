@echo off
setlocal
cd /d "%~dp0.."
title CLI - Live Attendance
color 0C

echo ============================================
echo  LIVE WEBCAM ATTENDANCE (CLI Mode)
echo ============================================
echo  Camera window mein 'q' dabao band karne ko
echo  Pehle ENROLL_STUDENT.bat se students enroll karo
echo ============================================
echo.

set /p SUBJECT="Subject naam likho (jaise AIML_LAB): "
if "%SUBJECT%"=="" (
    echo [ERROR] Subject zaroori hai!
    pause & exit /b 1
)

echo.
echo  Recognition shuru ho rahi hai...
echo  Camera window mein 'q' dabao quit karne ke liye
echo.

".venv\Scripts\python.exe" scripts\recognize.py --subject "%SUBJECT%"

echo.
pause
