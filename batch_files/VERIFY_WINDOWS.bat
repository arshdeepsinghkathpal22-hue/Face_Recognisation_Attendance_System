@echo off
setlocal
cd /d "%~dp0.."
title Verify - Face Recognition Attendance System
color 0D

echo ============================================
echo  VERIFY WINDOWS INSTALL
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv nahi mila. Pehle START.bat run karo.
    pause & exit /b 1
)

".venv\Scripts\python.exe" scripts\windows_preflight.py --mode all
if errorlevel 1 pause & exit /b 1

echo.
echo [TEST] Backend tests start ho rahe hain.
echo        Pytest fresh Python process mein dlib/face_recognition dobara load karega.
echo        Agar "collecting..." par rukta dikhe, wait karo. Ctrl+C mat dabana.
echo.
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
".venv\Scripts\python.exe" -m pytest -vv
if errorlevel 1 pause & exit /b 1

cd frontend
echo.
echo [BUILD] Frontend production build start ho raha hai.
echo.
npm run build
if errorlevel 1 (
    cd ..
    pause & exit /b 1
)
cd ..

echo.
echo [OK] Backend tests aur frontend build pass ho gaye.
pause
