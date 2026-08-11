@echo off
setlocal
cd /d "%~dp0.."
title BACKEND - Face Attendance

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe nahi mila. Pehle START.bat run karo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
pause
