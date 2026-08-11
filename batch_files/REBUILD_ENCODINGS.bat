@echo off
setlocal
cd /d "%~dp0.."
title Rebuild Face Encodings
color 0E

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv nahi mila. Pehle START.bat run karo.
    pause
    exit /b 1
)

echo ============================================
echo  REBUILD FACE ENCODINGS
echo ============================================
echo.
echo Photos yahan honi chahiye:
echo data\students\STUDENT_ID\photo1.jpg
echo.
echo dlib model first time load hone mein time lag sakta hai.
echo Window band ya Ctrl+C mat dabana jab tak processing start na ho.
echo.

".venv\Scripts\python.exe" rebuild_encodings.py
echo.
pause
