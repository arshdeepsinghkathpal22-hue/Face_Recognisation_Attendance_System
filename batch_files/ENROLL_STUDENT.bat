@echo off
setlocal
cd /d "%~dp0.."
title Student Enroll Karo
color 0E

echo ============================================
echo  STUDENT FACE ENROLLMENT
echo ============================================
echo.
echo  PEHLE student ki photos rakho:
echo  data\students\[STUDENT_ID]\photo1.jpg
echo  data\students\[STUDENT_ID]\photo2.jpg
echo  ... (5-15 photos, ek saaf chehra)
echo.
echo  START.bat pehle chalao agar nahi chala
echo ============================================
echo.

set /p STUDENT_ID="Student ID likho (jaise 22BCS001): "
set /p STUDENT_NAME="Student naam likho (jaise Rahul Sharma): "
set /p BRANCH="Branch (CSE/ECE/ME) [default=CSE]: "
if "%BRANCH%"=="" set BRANCH=CSE

echo.
echo  Enrolling: %STUDENT_NAME% (%STUDENT_ID%) - %BRANCH%
echo.

".venv\Scripts\python.exe" scripts\enroll.py ^
    --student-id "%STUDENT_ID%" ^
    --name "%STUDENT_NAME%" ^
    --branch "%BRANCH%"

if errorlevel 1 (
    echo.
    echo  [ERROR] Enrollment fail hua! Check karo:
    echo    - data\students\%STUDENT_ID%\ folder mein photos hain?
    echo    - Har photo mein ek saaf chehra hai?
    echo    - .jpg/.jpeg/.png format hai?
) else (
    echo.
    echo  [SUCCESS] %STUDENT_NAME% enroll ho gaya!
    echo            Ab portal se attendance le sakte ho.
)

echo.
pause
