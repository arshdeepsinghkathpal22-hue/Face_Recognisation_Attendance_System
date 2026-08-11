import { useEffect, useState } from "react";

import AdminStitchPage from "./pages/AdminStitchPage";
import LoginPage from "./pages/LoginPage";
import StudentStitchPage from "./pages/StudentStitchPage";
import TeacherStitchPage from "./pages/TeacherStitchPage";
import { Card, CardContent } from "@/components/ui/card";
import {
  getAdminMe,
  getMe,
  getTeacherMe,
  loginAdmin,
  loginStudent,
  loginTeacher,
  logoutAdmin,
  logoutStudent,
  logoutTeacher
} from "./services/api";

export default function App() {
  const [isInitializing, setIsInitializing] = useState(true);
  const [student, setStudent] = useState(null);
  const [teacher, setTeacher] = useState(null);
  const [admin, setAdmin] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function bootstrap() {
      try {
        const adminMe = await getAdminMe();
        if (adminMe.logged_in) {
          setAdmin(adminMe.admin);
          return;
        }

        const teacherMe = await getTeacherMe();
        if (teacherMe.logged_in) {
          setTeacher(teacherMe.teacher);
          return;
        }

        const studentMe = await getMe();
        if (studentMe.logged_in) {
          setStudent(studentMe.student);
        }
      } catch (apiError) {
        setError(apiError.message);
      } finally {
        setIsInitializing(false);
      }
    }
    bootstrap();
  }, []);

  async function handleStudentLogin(studentId, password) {
    setError("");
    const response = await loginStudent(studentId, password);
    setAdmin(null);
    setTeacher(null);
    setStudent(response.student);
  }

  async function handleTeacherLogin(teacherId, password) {
    setError("");
    const response = await loginTeacher(teacherId, password);
    setAdmin(null);
    setStudent(null);
    setTeacher(response.teacher);
  }

  async function handleAdminLogin(adminId, password) {
    setError("");
    const response = await loginAdmin(adminId, password);
    setStudent(null);
    setTeacher(null);
    setAdmin(response.admin);
  }

  async function handleStudentLogout() {
    setError("");
    try {
      await logoutStudent();
    } catch (apiError) {
      setError(apiError.message || "Failed to logout.");
    } finally {
      setStudent(null);
    }
  }

  async function handleTeacherLogout() {
    setError("");
    try {
      await logoutTeacher();
    } catch (apiError) {
      setError(apiError.message || "Failed to logout.");
    } finally {
      setTeacher(null);
    }
  }

  async function handleAdminLogout() {
    setError("");
    try {
      await logoutAdmin();
    } catch (apiError) {
      setError(apiError.message || "Failed to logout.");
    } finally {
      setAdmin(null);
    }
  }

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-md border-indigo-100 bg-white/90 shadow-xl shadow-indigo-100/70">
          <CardContent className="flex items-center justify-center py-10 text-center">
            <div>
              <p className="font-display text-4xl text-indigo-700">FACEGRID</p>
              <p className="mt-2 text-slate-600">Loading attendance workspace...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (admin) {
    return <AdminStitchPage admin={admin} onLogout={handleAdminLogout} />;
  }

  if (teacher) {
    return <TeacherStitchPage teacher={teacher} onLogout={handleTeacherLogout} />;
  }

  if (student) {
    return <StudentStitchPage student={student} onLogout={handleStudentLogout} />;
  }

  return (
    <LoginPage
      onStudentLogin={handleStudentLogin}
      onTeacherLogin={handleTeacherLogin}
      onAdminLogin={handleAdminLogin}
      error={error}
    />
  );
}
