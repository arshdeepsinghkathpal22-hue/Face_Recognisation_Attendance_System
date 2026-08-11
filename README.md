# FaceGrid - Face Recognition Attendance System

FaceGrid ek Windows-ready attendance portal hai jisme teacher live camera se attendance mark kar sakta hai, admin/student biometric profile register kar sakta hai, aur student apni attendance summary dekh sakta hai.

## Quick Start

### 1. Required Software

Install these first:

1. Python 3.10 ya 3.11 for Windows  
   Install karte time **Add python.exe to PATH** tick karo.
2. Node.js LTS  
   Download: <https://nodejs.org>
3. Agar `dlib` ya `face-recognition` install me error aaye, Visual Studio Build Tools install karo:

```bat
winget install Microsoft.VisualStudio.2022.BuildTools
```

Installer open hone ke baad **Desktop development with C++** select karo.

### 2. App Start Karna

Project folder me `START.bat` double-click karo.

`START.bat` ye sab automatically karega:

- Python version check
- Node.js check
- `.venv` virtual environment create
- Python dependencies install
- SQLite database `attendance.db` initialize
- Demo data seed
- Frontend dependencies install
- Backend API start
- Frontend portal start
- Browser open

URLs:

- Web Portal: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8000`

Important: Backend aur frontend ki jo command windows khulti hain unhe band mat karo. Dono windows band kar doge to app stop ho jayegi.

## Login Credentials

| Role | Login ID | Password |
| --- | --- | --- |
| Faculty / Teacher | `admin` | `admin` |
| Admin | `admin` | `admin` |
| Student | `22BCS001` | `22BCS001` |
| Student | `22BCS002` | `22BCS002` |

Student login me password same enrollment number hota hai.

## Teacher Portal - Kaise Use Karna Hai

1. Browser me `http://127.0.0.1:5173` open karo.
2. Login screen par **Faculty** select karo.
3. Employee ID: `admin`
4. Password: `admin`
5. Login ke baad teacher dashboard open hoga.
6. Class list me se class choose karo, jaise:
   - Computer Networks - F6
   - DAA Batch F5F6
   - DAA LAB F6
   - Competitive Programming Lab F5
   - Discrete Maths - F10
7. Kisi class ke saamne **Select** dabao.
8. App attendance session start karega aur live camera page kholega.
9. Browser camera permission maange to **Allow** karo.
10. Camera ke saamne enrolled student ka face aane par attendance automatically mark hogi.
11. Right side **Attendance Log** me marked students dikhenge.
12. Agar student selected batch/class se match nahi karta, batch mismatch warning aa sakti hai.
13. Class complete hone ke baad **Stop & Submit Attendance** dabao.
14. Logout ke liye top-right **Sign Out** use karo.

Teacher portal ki main functionality:

- Teacher login/logout
- Assigned classes load karna
- Subject, semester, batch ke basis par session start karna
- Live webcam attendance
- Face recognition ke through present mark karna
- Duplicate marking avoid karna
- Batch mismatch detect karna
- Attendance log live update
- Session stop/submit

## Student Portal - Kaise Use Karna Hai

1. Browser me `http://127.0.0.1:5173` open karo.
2. Login screen par **Student** select karo.
3. Enrollment Number enter karo, example: `22BCS001`.
4. Password me bhi same enrollment number enter karo: `22BCS001`.
5. Login ke baad student dashboard open hoga.

Student dashboard me ye dikhta hai:

- Student name
- Enrollment number
- Batch
- Total recorded attendance
- Subject-wise attendance
- Lecture percentage
- Practical percentage
- Overall percentage
- Low attendance warning color, agar attendance 75 percent se kam ho

Logout ke liye **Sign Out** dabao.

## Admin Portal - Kaise Use Karna Hai

1. Browser me `http://127.0.0.1:5173` open karo.
2. Login screen par **Admin** select karo.
3. Admin ID: `admin`
4. Password: `admin`
5. Login ke baad **Register Biometrics** page open hoga.

Naya student register karne ke steps:

1. Student Name fill karo.
2. Enrollment Number fill karo.
3. Batch select karo.
4. Student ki clear face images upload karo using **Browse Files**.
5. Ya **Capture Live Photo** se webcam se photo capture karo.
6. 1 se 10 images queue me add ho sakti hain.
7. **Register Profile** dabao.
8. System photos save karega, face encodings banayega, aur student DB me add/update karega.

Admin portal ki main functionality:

- Admin login/logout
- New teacher add/register
- Teacher ko subject, semester, batch, aur lecture/practical assignment dena
- Student biometric registration
- Multiple image upload
- Live camera photo capture
- Batch assign
- Face encoding rebuild/update
- Existing student profile update

Naya teacher add karne ke steps:

1. Admin portal me login karo: `admin` / `admin`.
2. Top par **Register New Teacher** panel dikhega.
3. Teacher ID fill karo, example: `faculty001`.
4. Teacher Name fill karo.
5. Password set karo.
6. Semester, Subject, Batch, aur Type select karo.
7. **Add Assignment** dabao.
8. Zarurat ho to multiple assignments add karo.
9. **Register Teacher** dabao.
10. Logout karke **Faculty** login me naye Teacher ID/password se login karo.

Note: Teacher sirf wahi classes dekh paayega jo admin ne assignment me add ki hain.

## Interview Demo Checklist

Interview se pehle ye quick flow run kar lo:

1. `VERIFY_WINDOWS.bat` double-click karo.
2. Output me backend tests aur frontend build pass hone chahiye.
3. `START.bat` double-click karo.
4. Browser me `http://127.0.0.1:5173` open ho jana chahiye.
5. Admin login karke ek new teacher add karo.
6. New teacher se Faculty login karke assigned class list check karo.
7. Teacher dashboard me class select karke camera permission allow karo.
8. Enrolled student ka face camera ke saamne lao aur attendance log verify karo.
9. Student login karke attendance summary page dikhao.

Interview me short explanation:

- Backend FastAPI hai.
- SQLite local database use ho raha hai.
- React + Vite frontend hai.
- Admin teacher/student registration kar sakta hai.
- Teacher assigned class ke liye live face attendance mark karta hai.
- Student apni attendance summary dekh sakta hai.

## Command Line Enrollment

Portal ke alawa CLI se bhi student enroll kar sakte ho.

1. Student photos is folder me rakho:

```text
data\students\[STUDENT_ID]\photo1.jpg
data\students\[STUDENT_ID]\photo2.jpg
data\students\[STUDENT_ID]\photo3.jpg
```

Example:

```text
data\students\22BCS010\photo1.jpg
data\students\22BCS010\photo2.jpg
```

Recommended: 5-15 clear photos, har photo me ek hi saaf face.

2. `ENROLL_STUDENT.bat` double-click karo.
3. Student ID, name, branch enter karo.
4. Script student profile aur face encodings create karegi.

## CLI Attendance Mode

Web portal ke bina command-line webcam attendance bhi available hai.

1. Pehle students enroll hone chahiye.
2. `CLI_ATTENDANCE.bat` double-click karo.
3. Subject name enter karo, example: `AIML_LAB`.
4. Camera window open hogi.
5. Face recognize hone par attendance mark hogi.
6. Quit karne ke liye camera window me `q` press karo.

## Useful Batch Files

| File | Use |
| --- | --- |
| `START.bat` | Full setup + backend + frontend start |
| `SETUP_WINDOWS.bat` | Setup helper, internally `START.bat` call karta hai |
| `RUN_BACKEND.bat` | Sirf backend API start karta hai |
| `RUN_FRONTEND.bat` | Sirf frontend dev server start karta hai |
| `VERIFY_WINDOWS.bat` | Python checks, backend tests, frontend build verify karta hai |
| `ENROLL_STUDENT.bat` | Photos folder se student enroll karta hai |
| `CLI_ATTENDANCE.bat` | Command-line webcam attendance start karta hai |
| `REBUILD_ENCODINGS.bat` | Existing student photos se encodings dobara banata hai |

## Manual Run Commands

Normally `START.bat` enough hai. Manual run karna ho to:

Backend:

```bat
.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bat
cd frontend
npm run dev
```

Database initialize:

```bat
.venv\Scripts\python.exe scripts\init_db.py
```

Demo data seed:

```bat
.venv\Scripts\python.exe scripts\seed_portal_data.py --file data\seed\portal_seed.json
```

All face encodings rebuild:

```bat
.venv\Scripts\python.exe rebuild_encodings.py
```

## Verification

Full verification ke liye `VERIFY_WINDOWS.bat` double-click karo.

Manual commands:

```bat
.venv\Scripts\python.exe scripts\windows_preflight.py --mode all
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

## Folder Structure

```text
app\                    Backend app
app\api\                FastAPI routes
app\services\           Attendance service logic
frontend\               React + Vite frontend
frontend\src\pages\     Login, teacher, admin, student pages
frontend\stitch_exports Static HTML templates used inside portal iframes
scripts\                Setup, seed, enroll, recognition helper scripts
data\seed\              Demo portal data
data\students\          Student face image folders
tests\                  Backend/API tests
attendance.db           Local SQLite database, created after setup
encodings.pkl           Face encodings file, created after enrollment
```

## Troubleshooting

### Python nahi mil raha

Python 3.10/3.11 install karo aur PATH me add karo. Phir terminal/batch dobara open karo.

### `dlib` ya `face-recognition` install fail

Visual Studio Build Tools install karo aur **Desktop development with C++** select karo. Phir `START.bat` dobara run karo.

### Camera open nahi ho raha

- Browser permission me camera allow karo.
- Dusri app camera use kar rahi ho to close karo.
- Portal `http://127.0.0.1:5173` par hi open karo.

### Student recognize nahi ho raha

- Student pehle enroll hona chahiye.
- Photos clear honi chahiye.
- Har image me ek saaf face hona chahiye.
- Different angles/light me 5-15 photos better result deti hain.
- `REBUILD_ENCODINGS.bat` run karke encodings refresh karo.

### Attendance mark nahi ho rahi

- Teacher ne correct class/batch select ki hai ya nahi check karo.
- Student ka batch profile selected class se match hona chahiye.
- Camera page par live feed aa rahi hai ya nahi check karo.
- Backend window me error logs check karo.

## Features Summary

- Role-based portal: Teacher, Student, Admin
- Session-based attendance
- Live webcam face recognition
- Automatic attendance marking
- Batch mismatch handling
- Student biometric registration
- File upload and live camera capture for registration
- Student attendance dashboard
- Subject-wise and total attendance percentages
- SQLite local database
- Windows one-click startup scripts
- Backend API tests and frontend build verification

## Tech Stack - Short

Backend:

- Python
- FastAPI
- Uvicorn
- Starlette sessions via `itsdangerous`
- `python-multipart` for image uploads
- Pytest + HTTPX for tests

AI / Face Recognition:

- `face-recognition`
- `dlib`
- OpenCV (`opencv-python`)
- NumPy
- Pickle-based face encoding storage

Frontend:

- React 18
- Vite
- Tailwind CSS
- shadcn-style UI components
- Radix UI
- Lucide React icons
- Static Stitch HTML templates embedded through iframes

Database:

- SQLite
- Local file: `attendance.db`

Platform / Scripts:

- Windows batch files (`.bat`)
- Python virtual environment: `.venv`
- npm for frontend packages
