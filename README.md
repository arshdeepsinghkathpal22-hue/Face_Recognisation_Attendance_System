# Face Recognition Attendance System

This project is a face recognition-based attendance system designed for educational institutions. It provides a web portal for teachers to mark attendance using a live camera feed, an admin panel for managing student and teacher data, and a dashboard for students to view their attendance records.

## Features

*   **Role-Based Access**: Separate portals for Admin, Teacher, and Student roles.
*   **Live Attendance**: Teachers can start a class session and mark attendance in real-time using a webcam.
*   **Student Enrollment**: Admins can register new students by uploading face images or capturing them live.
*   **Teacher & Class Management**: Admins can register teachers and assign them to specific subjects, semesters, and batches.
*   **Attendance Dashboard**: Students can log in to view their overall and subject-wise attendance percentages.
*   **Batch Validation**: The system checks if a recognized student belongs to the correct batch for the ongoing class session.
*   **Local Database**: Uses SQLite for simple, file-based data storage.
*   **Windows Scripts**: Includes batch scripts for easy setup and execution on Windows.

## Technology Stack

*   **Backend**:
    *   Python 3.10 / 3.11
    *   FastAPI
    *   Uvicorn
    *   Pytest for testing
*   **Face Recognition**:
    *   `face-recognition` library (built on `dlib`)
    *   OpenCV (`opencv-python`)
    *   HOG-based model for face detection
    *   ResNet-based model for 128-d facial embeddings
    *   NumPy
*   **Frontend**:
    *   React 18
    *   Vite
    *   Tailwind CSS
    *   shadcn/ui & Radix UI for components
*   **Database**:
    *   SQLite

## Project Structure

```
app/                    # FastAPI backend source code
├── api/                # API route definitions (teacher, student, admin)
└── services/           # Business logic for enrollment and attendance
frontend/               # React frontend source code
├── src/pages/          # Main pages for each user role
└── src/components/     # Reusable React components
scripts/                # Helper scripts for setup, db init, and enrollment
data/
├── students/           # Stores student face images, organized by student ID
└── seed/               # JSON file with initial data for seeding
tests/                  # Backend API tests
batch_files/            # Utility .bat scripts
attendance.db           # SQLite database file (created on first run)
encodings.pkl           # Stores generated face encodings (created after enrollment)
```

## Setup and Installation

This project is optimized for Windows.

### 1. Prerequisites

1.  **Python**: Version 3.10 or 3.11. During installation, ensure you check **"Add python.exe to PATH"**.
2.  **Node.js**: LTS version. Download from nodejs.org.
3.  **C++ Build Tools**: Required for compiling the `dlib` dependency. If you encounter errors during package installation, install Visual Studio Build Tools.
    ```sh
    winget install Microsoft.VisualStudio.2022.BuildTools
    ```
    In the installer, select the **"Desktop development with C++"** workload.

### 2. Running the Application

The simplest way to get started is to use the main startup script.

1.  Double-click `START.bat` in the project's root directory.

This script automates the entire setup process:
*   Checks for Python and Node.js.
*   Creates a Python virtual environment (`.venv`).
*   Installs all required Python (`requirements.txt`) and Node.js (`package.json`) dependencies.
*   Initializes the SQLite database (`attendance.db`) and seeds it with sample data on the first run.
*   Starts the backend and frontend servers in separate terminal windows.
*   Opens the web portal in your default browser.

**Important**: Do not close the two new terminal windows that open (one for the backend, one for the frontend). Closing them will stop the application.

*   **Web Portal**: `http://127.0.0.1:5173`
*   **Backend API**: `http://127.0.0.1:8000`

## Application Walkthrough

### Default Login Credentials

| Role | Login ID | Password |
| --- | --- | --- |
| Admin / Teacher | `admin` | `admin` |
| Student | `22BCS001` | `22BCS001` |
| Student | `22BCS002` | `22BCS002` |

### 1. Admin: Register a Teacher

1.  Log in as **Admin** (`admin`/`admin`).
2.  Use the "Register New Teacher" panel to create a new teacher profile.
3.  Assign subjects, semesters, and batches to the teacher.
4.  Click **Register Teacher**.

### 2. Admin: Enroll a Student

1.  On the Admin dashboard, stay on the "Register Biometrics" page.
2.  Fill in the student's details (Name, Enrollment No, Batch).
3.  Upload 5-10 clear photos of the student's face or use the webcam to capture them.
4.  Click **Register Profile**. The system will process the images, generate face encodings, and save the student's profile.

### 3. Teacher: Take Attendance

1.  Log out and log back in as **Faculty** using the credentials you created.
2.  The dashboard will show the classes assigned to you.
3.  Click **Select** next to a class to start an attendance session.
4.  Allow browser permission for the camera.
5.  As enrolled students appear before the camera, their attendance will be marked automatically and will appear in the "Attendance Log".
6.  Once the class is over, click **Stop & Submit Attendance**.

### 4. Student: View Attendance

1.  Log in as **Student** (e.g., `22BCS001`/`22BCS001`).
2.  The dashboard displays the student's attendance summary, including overall and subject-wise percentages.

## Command-Line Utilities

The project includes several batch scripts for common operations.

### Student Enrollment via CLI

You can enroll a student directly from image files without using the web UI.

1.  Create a folder for the student inside `data/students/` using their ID as the folder name.
2.  Place their face images (e.g., `.jpg`, `.png`) inside this folder.
    ```
    data/students/22BCS010/photo1.jpg
    data/students/22BCS010/photo2.jpg
    ```
3.  Double-click `ENROLL_STUDENT.bat`.
4.  Follow the prompts to enter the student's ID, name, and branch. The script will then generate and save the face encodings.

### Rebuild All Encodings

If you add or change student photos manually, you may need to rebuild the entire `encodings.pkl` file.

*   Run `REBUILD_ENCODINGS.bat` to re-process all images in the `data/students/` directory.

### Other Scripts

| File | Description |
| --- | --- |
| `START.bat` | Full setup and application launch. |
| `VERIFY_WINDOWS.bat` | Runs pre-flight checks, backend tests, and a frontend build. |
| `RUN_BACKEND.bat` | Starts only the backend server. |
| `RUN_FRONTEND.bat` | Starts only the frontend development server. |
| `CLI_ATTENDANCE.bat` | A basic CLI-only attendance mode (requires enrolled students). |

## Testing

To verify the installation and ensure both the backend and frontend are working correctly, run `VERIFY_WINDOWS.bat`.

This script will:
1.  Run Python environment checks.
2.  Execute backend API tests using `pytest`.
3.  Attempt a production build of the frontend using `npm run build`.

## Troubleshooting

*   **`dlib` or `face-recognition` install fails**: This is almost always due to missing C++ build tools. Follow step 3 in the Prerequisites section.
*   **Python not found**: Make sure you installed Python 3.10 or 3.11 and that it was added to your system's PATH.
*   **Camera not opening**:
    *   Ensure you granted camera permissions to the browser for `http://127.0.0.1:5173`.
    *   Check that no other application is using your webcam.
*   **Student not recognized**:
    *   Ensure the student is enrolled via the Admin portal or CLI script.
    *   Use clear, well-lit photos for enrollment. 5-15 photos with varied angles are recommended for better accuracy.
    *   Run `REBUILD_ENCODINGS.bat` to refresh the encodings file after adding new photos manually.
*   **Attendance not marked**:
    *   Verify the teacher has selected the correct class session.
    *   Check if the student's registered batch matches the batch of the class session. The system will show a "batch mismatch" warning if they don't align.
