from pydantic import BaseModel


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


class AttendanceRowResponse(BaseModel):
    sl_no: int
    subject_name: str
    current_l_pct: int | None
    current_p_pct: int | None
    overall_pct: int | None


class AttendanceSummaryResponse(BaseModel):
    semester: SemesterResponse
    total_held: int
    total_attended: int
    total_pct: int | None
    rows: list[AttendanceRowResponse]


class TeacherResponse(BaseModel):
    teacher_id: str
    name: str


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


class TeacherRegisterRequest(BaseModel):
    teacher_id: str
    name: str
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


class FrameProcessResponse(BaseModel):
    session_id: int
    marked_in_frame: list[FrameDetectionResponse]
    present_students: list[StudentResponse]


class SessionAttendanceResponse(BaseModel):
    session_id: int
    present_students: list[StudentResponse]


class StudentRegisterResponse(BaseModel):
    ok: bool
    student: StudentResponse
    uploaded_images: int
    valid_images: int
