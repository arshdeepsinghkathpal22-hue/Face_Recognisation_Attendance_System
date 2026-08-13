const BASE_HEADERS = {
  "Content-Type": "application/json"
};

async function parseResponse(response) {
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_error) {
    data = { detail: text || "Request failed" };
  }
  if (!response.ok) {
    const detail = data?.detail || "Request failed";
    if (typeof detail === "object" && detail !== null) {
      const error = new Error(detail.message || "Request failed");
      error.detail = detail;
      error.status = response.status;
      throw error;
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return data;
}

export async function getMe() {
  const response = await fetch("/api/me", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function loginStudent(studentId, password) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify({ student_id: studentId, password })
  });
  return parseResponse(response);
}

export async function logoutStudent() {
  const response = await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getSemesters() {
  const response = await fetch("/api/semesters", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherMe() {
  const response = await fetch("/api/teacher/me", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getAdminMe() {
  const response = await fetch("/api/admin/me", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function loginTeacher(teacherId, password) {
  const response = await fetch("/api/teacher/auth/login", {
    method: "POST",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify({ teacher_id: teacherId, password })
  });
  return parseResponse(response);
}

export async function loginAdmin(adminId, password) {
  const response = await fetch("/api/admin/auth/login", {
    method: "POST",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify({ admin_id: adminId, password })
  });
  return parseResponse(response);
}

export async function logoutTeacher() {
  const response = await fetch("/api/teacher/auth/logout", {
    method: "POST",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function logoutAdmin() {
  const response = await fetch("/api/admin/auth/logout", {
    method: "POST",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherSemesters() {
  const response = await fetch("/api/teacher/semesters", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherBatches() {
  const response = await fetch("/api/teacher/batches", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherSubjects(semesterId) {
  const params = new URLSearchParams({ semester_id: semesterId });
  const response = await fetch(`/api/teacher/subjects?${params.toString()}`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherAssignments() {
  const response = await fetch("/api/teacher/assignments", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function startTeacherSession(payload) {
  const response = await fetch("/api/teacher/sessions/start", {
    method: "POST",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function stopTeacherSession(sessionId) {
  const response = await fetch(`/api/teacher/sessions/${sessionId}/stop`, {
    method: "POST",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function processTeacherFrame(sessionId, blob, tolerance = 0.5, mode = "detect") {
  const formData = new FormData();
  formData.append("frame", blob, "frame.jpg");
  formData.append("tolerance", String(tolerance));
  formData.append("mode", mode);
  const response = await fetch(`/api/teacher/sessions/${sessionId}/frame`, {
    method: "POST",
    credentials: "include",
    body: formData
  });
  return parseResponse(response);
}

export async function getTeacherSessionAttendance(sessionId) {
  const response = await fetch(`/api/teacher/sessions/${sessionId}/attendance`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function registerTeacherStudent(payload) {
  const formData = new FormData();
  formData.append("student_id", payload.student_id);
  formData.append("name", payload.name);
  formData.append("branch", payload.branch);
  formData.append("batch", payload.batch);
  payload.images.forEach((file) => {
    formData.append("images", file);
  });

  const response = await fetch("/api/teacher/students/register", {
    method: "POST",
    credentials: "include",
    body: formData
  });
  return parseResponse(response);
}

export async function registerAdminStudent(payload) {
  const formData = new FormData();
  formData.append("student_id", payload.student_id);
  formData.append("name", payload.name);
  formData.append("branch", payload.branch);
  formData.append("batch", payload.batch);
  payload.images.forEach((file) => {
    formData.append("images", file);
  });

  const response = await fetch("/api/admin/students/register", {
    method: "POST",
    credentials: "include",
    body: formData
  });
  return parseResponse(response);
}

export async function getAdminTeacherOptions() {
  const response = await fetch("/api/admin/teacher-options", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function registerAdminTeacher(payload) {
  const response = await fetch("/api/admin/teachers/register", {
    method: "POST",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function getAdminTeachers() {
  const response = await fetch("/api/admin/teachers", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getAdminStudents() {
  const response = await fetch("/api/admin/students", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getAttendanceSummary(semesterId) {
  const params = new URLSearchParams({ semester_id: semesterId });
  const response = await fetch(`/api/attendance/summary?${params.toString()}`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getAdminDashboardStats(semesterId = "fall-2024") {
  const params = new URLSearchParams({ semester_id: semesterId });
  const response = await fetch(`/api/admin/dashboard-stats?${params.toString()}`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function createAdminSubject(payload) {
  const response = await fetch("/api/admin/subjects", {
    method: "POST",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function updateAdminSubject(subjectId, payload, semesterId = "fall-2024") {
  const params = new URLSearchParams({ semester_id: semesterId });
  const response = await fetch(`/api/admin/subjects/${subjectId}?${params.toString()}`, {
    method: "PUT",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function deleteAdminSubject(subjectId, semesterId = "fall-2024") {
  const params = new URLSearchParams({ semester_id: semesterId });
  const response = await fetch(`/api/admin/subjects/${subjectId}?${params.toString()}`, {
    method: "DELETE",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function updateAdminStudent(studentId, payload) {
  const response = await fetch(`/api/admin/students/${studentId}`, {
    method: "PUT",
    credentials: "include",
    headers: BASE_HEADERS,
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function deleteAdminStudent(studentId) {
  const response = await fetch(`/api/admin/students/${studentId}`, {
    method: "DELETE",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function deleteAdminTeacher(teacherId) {
  const response = await fetch(`/api/admin/teachers/${teacherId}`, {
    method: "DELETE",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherSessionHistory() {
  const response = await fetch("/api/teacher/sessions/history", {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getTeacherSessionRoster(sessionId) {
  const response = await fetch(`/api/teacher/sessions/${sessionId}/roster`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

export async function getStudentAttendanceHistory(semesterId = "fall-2024") {
  const params = new URLSearchParams({ semester_id: semesterId });
  const response = await fetch(`/api/attendance/history?${params.toString()}`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse(response);
}

