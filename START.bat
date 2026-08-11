@echo off
setlocal EnableDelayedExpansion
title Face Recognition Attendance System
color 0A
cd /d "%~dp0"

echo.
echo  =====================================================
echo   FACE RECOGNITION ATTENDANCE SYSTEM
echo  =====================================================
echo.

:: ── Step 1: Python check ────────────────────────────────
set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.10 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.10"
    if not defined PYTHON_CMD (
        py -3.11 --version >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=py -3.11"
    )
)
if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    color 0C
    echo  [ERROR] Python nahi mila!
    echo          Python 3.10 ya 3.11 install karo aur PATH mein add karo.
    echo          https://www.python.org/downloads/windows/
    echo.
    pause & exit /b 1
)
%PYTHON_CMD% scripts\windows_preflight.py --mode python
if errorlevel 1 (
    color 0C
    echo.
    echo  [ERROR] Is project ke liye Windows par Python 3.10/3.11 use karo.
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% mila

:: ── Step 2: Node.js check ───────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo  [ERROR] Node.js nahi mila!
    echo          https://nodejs.org se LTS version install karo.
    echo.
    pause & exit /b 1
)
for /f %%v in ('node --version') do set NODEVER=%%v
echo  [OK] Node.js %NODEVER% mila

:: ── Step 3: Virtual environment ─────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  [SETUP] Virtual environment bana raha hai...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        color 0C
        echo  [ERROR] .venv nahi bana!
        pause & exit /b 1
    )
    echo  [OK] .venv bana gaya
)

".venv\Scripts\python.exe" scripts\windows_preflight.py --mode dirs
".venv\Scripts\python.exe" scripts\windows_preflight.py --mode imports
if errorlevel 1 (
    echo.
    echo  [SETUP] Missing Python packages mil gaye.
    echo          Install ho raha hai. Ctrl+C ya terminal close mat karna.
    echo.
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip "setuptools<81" wheel cmake
    if errorlevel 1 (
        color 0C
        echo.
        echo  [ERROR] pip/tools install fail hua.
        echo          Agar tumne Ctrl+C dabaya tha, START.bat dobara run karo.
        pause & exit /b 1
    )

    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        color 0C
        echo.
        echo  [ERROR] Python packages install fail hua.
        echo          Agar dlib/face-recognition fail ho, Visual Studio Build Tools install karo:
        echo          winget install Microsoft.VisualStudio.2022.BuildTools
        echo          Installer mein "Desktop development with C++" select karo.
        echo.
        pause & exit /b 1
    )

    ".venv\Scripts\python.exe" scripts\windows_preflight.py --mode imports
    if errorlevel 1 (
        color 0C
        echo  [ERROR] Python dependency verification fail hua.
        pause & exit /b 1
    )
    echo  [OK] Packages install ho gayi
) else (
    echo  [OK] Python packages already ready hain
)

:: ── Step 4: Database initialize ─────────────────────────
if not exist "attendance.db" (
    echo.
    echo  [SETUP] Database initialize ho raha hai...
    ".venv\Scripts\python.exe" scripts\init_db.py
    if errorlevel 1 (
        color 0C
        echo  [ERROR] Database init fail hua!
        pause & exit /b 1
    )
    echo  [OK] Database ready

    echo  [SETUP] Sample data load ho raha hai...
    ".venv\Scripts\python.exe" scripts\seed_portal_data.py --file data\seed\portal_seed.json
    if errorlevel 1 (
        color 0C
        echo  [ERROR] Seed data load fail hua!
        pause & exit /b 1
    )
    echo  [OK] Seed data loaded
) else (
    echo  [OK] Database already hai
)

:: ── Step 5: npm install ──────────────────────────────────
if not exist "frontend\node_modules" (
    echo.
    echo  [SETUP] Frontend packages install ho rahi hain...
    cd frontend
    npm install --silent
    if errorlevel 1 (
        color 0C
        echo  [ERROR] npm install fail hua!
        cd ..
        pause & exit /b 1
    )
    cd ..
    echo  [OK] Frontend packages ready
) else (
    echo  [OK] node_modules already hain
)

:: ── Step 6: Launch ──────────────────────────────────────
echo.
echo  =====================================================
echo   Sab ready hai! System start ho raha hai...
echo  =====================================================
echo.
echo   Backend API : http://127.0.0.1:8000
echo   Web Portal  : http://127.0.0.1:5173
echo.
echo   Login:  Admin = admin / admin
echo           Teachers are created from the Admin panel
echo           Student       = 22BCS001 ya 22BCS002
echo.
echo   Dono windows band karne se system stop hoga.
echo  =====================================================
echo.

timeout /t 2 /nobreak >nul

:: Start backend in new window
start "BACKEND (band mat karo)" "%~dp0batch_files\RUN_BACKEND.bat"

:: Wait for backend to start
echo  [INFO] Backend start ho raha hai (5 sec)...
timeout /t 5 /nobreak >nul

:: Start frontend in new window
start "FRONTEND (band mat karo)" "%~dp0batch_files\RUN_FRONTEND.bat"

:: Wait then open browser
echo  [INFO] Browser khul raha hai...
timeout /t 4 /nobreak >nul
start http://127.0.0.1:5173

echo.
echo  [DONE] System chal raha hai!
echo         Ye window band kar sakte ho.
echo.
pause
