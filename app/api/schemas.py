from typing import Any

from pydantic import BaseModel, Field


class StudentResponse(BaseModel):
    student_id: str
    name: str
    branch: str = ""
    batch: str = ""


class LoginRequest(BaseModel):
    student_id: str
    password: str


class LoginResponse(BaseModel):
    ok: bool
    student: StudentResponse


class MeResponse(BaseModel):
    logged_in: bool
    student: StudentResponse | None


class SemesterResponse(BaseModel):
    id: str
    label: str


class SemestersListResponse(BaseModel):
    items: list[SemesterResponse]


class AttendanceTypeBreakdownResponse(BaseModel):
    attended: int
    held: int
    pct: int | None


class AttendanceRowResponse(BaseModel):
    sl_no: int
    subject_id: str
    subject_name: str
    held_l: int = 0
    held_t: int = 0
    held_p: int = 0
    attended_l: int = 0
    attended_t: int = 0
    attended_p: int = 0
    current_l_pct: int | None
    current_t_pct: int | None = None
    current_p_pct: int | None
    overall_pct: int | None
    lecture: AttendanceTypeBreakdownResponse
    tutorial: AttendanceTypeBreakdownResponse
    practical: AttendanceTypeBreakdownResponse
    overall: AttendanceTypeBreakdownResponse


class AttendanceSummaryResponse(BaseModel):
    semester: SemesterResponse
    total_held: int
    total_attended: int
    total_pct: int | None
    rows: list[AttendanceRowResponse]


class TeacherResponse(BaseModel):
    teacher_id: str
    name: str
    email: str = ""


class TeacherLoginRequest(BaseModel):
    teacher_id: str
    password: str


class TeacherLoginResponse(BaseModel):
    ok: bool
    teacher: TeacherResponse


class TeacherMeResponse(BaseModel):
    logged_in: bool
    teacher: TeacherResponse | None


class AdminResponse(BaseModel):
    admin_id: str
    name: str


class AdminLoginRequest(BaseModel):
    admin_id: str
    password: str


class AdminLoginResponse(BaseModel):
    ok: bool
    admin: AdminResponse


class AdminMeResponse(BaseModel):
    logged_in: bool
    admin: AdminResponse | None


class BatchesResponse(BaseModel):
    items: list[str]


class SubjectResponse(BaseModel):
    id: str
    name: str


class SubjectListResponse(BaseModel):
    items: list[SubjectResponse]


class AdminSubjectOptionResponse(BaseModel):
    id: str
    name: str


class AdminSemesterOptionResponse(BaseModel):
    id: str
    label: str
    subjects: list[AdminSubjectOptionResponse]


class AdminTeacherOptionsResponse(BaseModel):
    semesters: list[AdminSemesterOptionResponse]
    batches: list[str]


class TeacherAssignmentInput(BaseModel):
    semester_id: str
    subject_id: str
    batch: str
    class_type: str


class TeacherAssignmentRequest(BaseModel):
    semester_id: str
    subject_id: str
    batch: str
    class_type: str


class TeacherRegisterRequest(BaseModel):
    teacher_id: str
    name: str
    email: str = ""
    password: str
    assignments: list[TeacherAssignmentInput]


class TeacherAssignmentResponse(BaseModel):
    id: int
    teacher_id: str
    semester_id: str
    semester_label: str
    subject_id: str
    subject_name: str
    batch: str
    class_type: str


class TeacherRegisterResponse(BaseModel):
    ok: bool
    teacher: TeacherResponse
    assignments: list[TeacherAssignmentResponse]


class AdminTeachersListResponse(BaseModel):
    items: list[TeacherResponse]


class AdminStudentsListResponse(BaseModel):
    items: list[StudentResponse]


class StudentSubjectInput(BaseModel):
    semester_id: str
    subject_id: str


class StudentSubjectResponse(BaseModel):
    id: int
    student_id: str
    semester_id: str
    semester_label: str
    subject_id: str
    subject_name: str


class StudentSubjectsUpdateRequest(BaseModel):
    subjects: list[StudentSubjectInput]


class StudentSubjectsResponse(BaseModel):
    student_id: str
    subjects: list[StudentSubjectResponse]


class TeacherAssignmentsResponse(BaseModel):
    items: list[TeacherAssignmentResponse]


class StartClassSessionRequest(BaseModel):
    batch: str
    semester_id: str
    subject_id: str
    class_type: str
    start_time: str
    end_time: str


class ClassSessionResponse(BaseModel):
    session_id: int
    batch: str
    semester_id: str
    subject_id: str
    subject_name: str
    class_type: str
    session_date: str
    start_time: str | None
    end_time: str | None
    is_active: bool


class FrameDetectionResponse(BaseModel):
    student_id: str
    name: str
    distance: float
    status: str = "registered"
    warning: str | None = None
    debug: dict[str, Any] | None = None


class FrameProcessResponse(BaseModel):
    session_id: int
    marked_in_frame: list[FrameDetectionResponse]
    present_students: list[StudentResponse]
    debug: dict[str, Any] | None = None


class SessionAttendanceResponse(BaseModel):
    session_id: int
    present_students: list[StudentResponse]


class EnrollmentImageResultResponse(BaseModel):
    filename: str
    accepted: bool
    message: str


class StudentRegisterResponse(BaseModel):
    ok: bool
    student: StudentResponse
    uploaded_images: int
    valid_images: int
    rejected_images: int = 0
    results: list[EnrollmentImageResultResponse] = Field(default_factory=list)


class SubjectCreateRequest(BaseModel):
    id: str
    semester_id: str
    name: str
    sort_order: int = 1


class SubjectUpdateRequest(BaseModel):
    name: str
    sort_order: int = 1


class StudentUpdateRequest(BaseModel):
    name: str
    branch: str
    batch: str = ""


class TeacherUpdateRequest(BaseModel):
    name: str
    email: str = ""
    password: str = ""


class RecentAttendanceResponse(BaseModel):
    student_id: str
    student_name: str
    subject_id: str
    subject_name: str
    session_date: str
    class_type: str
    present: int


class AdminDashboardStatsResponse(BaseModel):
    total_students: int
    total_teachers: int
    total_subjects: int
    total_sessions: int
    overall_pct: int
    recent_attendance: list[RecentAttendanceResponse]


class TeacherSessionHistoryItemResponse(BaseModel):
    session_id: int
    subject_id: str
    subject_name: str
    semester_id: str
    class_type: str
    session_date: str
    batch: str
    start_time: str | None = None
    end_time: str | None = None
    is_active: bool
    marked_students: int
    present_students: int


class SessionRosterItemResponse(BaseModel):
    student_id: str
    name: str
    branch: str
    batch: str
    present: int


class StudentAttendanceHistoryItemResponse(BaseModel):
    session_id: int
    session_date: str
    start_time: str | None = None
    end_time: str | None = None
    class_type: str
    subject_id: str
    subject_name: str
    present: int

