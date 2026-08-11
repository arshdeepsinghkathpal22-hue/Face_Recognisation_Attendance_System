@echo off
setlocal
cd /d "%~dp0..\frontend"
title FRONTEND - Face Attendance

if not exist "package.json" (
    echo [ERROR] frontend\package.json nahi mila.
    pause
    exit /b 1
)

npm run dev
pause
