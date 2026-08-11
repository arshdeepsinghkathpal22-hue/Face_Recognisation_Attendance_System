from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
    AdminResponse,
    AdminSemesterOptionResponse,
    AdminSubjectOptionResponse,
    AdminTeacherOptionsResponse,
    StudentRegisterResponse,
    StudentResponse,
    TeacherAssignmentResponse,
    TeacherRegisterRequest,
    TeacherRegisterResponse,
    TeacherResponse,
)
from app.config import ENCODINGS_PATH, STUDENTS_DIR
from app.db import (
    get_admin_user,
    get_student_with_profile,
    list_active_semesters,
    list_batches,
    list_subjects_for_semester,
    list_teacher_assignments,
    replace_teacher_assignments,
    upsert_student,
    upsert_student_profile,
    upsert_teacher_user,
)
from app.face_utils import enroll_from_images

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_authenticated_admin(request: Request) -> AdminResponse:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    admin = get_admin_user(admin_id=admin_id, db_path=request.app.state.db_path)
    if admin is None:
        request.session.pop("admin_id", None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return AdminResponse(admin_id=admin["admin_id"], name=admin["name"])


@router.post("/auth/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, request: Request) -> AdminLoginResponse:
    admin = get_admin_user(admin_id=payload.admin_id, db_path=request.app.state.db_path)
    if admin is None or admin["password"] != payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

    request.session["admin_id"] = payload.admin_id
    request.session.pop("teacher_id", None)
    request.session.pop("student_id", None)
    return AdminLoginResponse(
        ok=True,
        admin=AdminResponse(admin_id=admin["admin_id"], name=admin["name"]),
    )


@router.post("/auth/logout")
def admin_logout(request: Request) -> dict:
    request.session.pop("admin_id", None)
    return {"ok": True}


@router.get("/me", response_model=AdminMeResponse)
def admin_me(request: Request) -> AdminMeResponse:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        return AdminMeResponse(logged_in=False, admin=None)

    admin = get_admin_user(admin_id=admin_id, db_path=request.app.state.db_path)
    if admin is None:
        request.session.pop("admin_id", None)
        return AdminMeResponse(logged_in=False, admin=None)

    return AdminMeResponse(
        logged_in=True,
        admin=AdminResponse(admin_id=admin["admin_id"], name=admin["name"]),
    )


@router.get("/teacher-options", response_model=AdminTeacherOptionsResponse)
def admin_teacher_options(
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> AdminTeacherOptionsResponse:
    semesters_payload: list[AdminSemesterOptionResponse] = []
    for semester in list_active_semesters(db_path=request.app.state.db_path):
        subjects = list_subjects_for_semester(
            semester_id=semester["id"],
            db_path=request.app.state.db_path,
        )
        semesters_payload.append(
            AdminSemesterOptionResponse(
                id=semester["id"],
                label=semester["label"],
                subjects=[AdminSubjectOptionResponse(**subject) for subject in subjects],
            )
        )

    batch_options = list(dict.fromkeys([*list_batches(db_path=request.app.state.db_path), "CSE", "CSE-F5", "CSE-F6", "CSE-F10", "F5", "F6", "F10", "F5F6"]))

    return AdminTeacherOptionsResponse(
        semesters=semesters_payload,
        batches=batch_options,
    )


@router.post("/teachers/register", response_model=TeacherRegisterResponse)
def register_teacher_via_admin(
    payload: TeacherRegisterRequest,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> TeacherRegisterResponse:
    db_path = request.app.state.db_path
    teacher_id = payload.teacher_id.strip()
    teacher_name = payload.name.strip()
    password = payload.password.strip()

    if not teacher_id or not teacher_name or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Teacher ID, name, and password are required")
    if not payload.assignments:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add at least one subject/batch assignment")

    normalized_assignments = []
    for assignment in payload.assignments:
        semester_id = assignment.semester_id.strip()
        subject_id = assignment.subject_id.strip()
        batch = assignment.batch.strip()
        class_type = assignment.class_type.strip().upper()
        if not semester_id or not subject_id or not batch:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment semester, subject, and batch are required")
        if class_type not in {"L", "P"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class type must be L or P")

        subjects = list_subjects_for_semester(semester_id=semester_id, db_path=db_path)
        if not any(subject["id"] == subject_id for subject in subjects):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject does not belong to selected semester")

        normalized_assignments.append(
            {
                "semester_id": semester_id,
                "subject_id": subject_id,
                "batch": batch,
                "class_type": class_type,
            }
        )

    upsert_teacher_user(
        teacher_id=teacher_id,
        name=teacher_name,
        password=password,
        db_path=db_path,
    )
    replace_teacher_assignments(
        teacher_id=teacher_id,
        assignments=normalized_assignments,
        db_path=db_path,
    )
    assignments = list_teacher_assignments(teacher_id=teacher_id, db_path=db_path)

    return TeacherRegisterResponse(
        ok=True,
        teacher=TeacherResponse(teacher_id=teacher_id, name=teacher_name),
        assignments=[TeacherAssignmentResponse(**item) for item in assignments],
    )


@router.post("/students/register", response_model=StudentRegisterResponse)
async def register_student_via_admin(
    request: Request,
    student_id: str = Form(..., min_length=1),
    name: str = Form(..., min_length=1),
    branch: str = Form(..., min_length=1),
    batch: str = Form(""),
    images: list[UploadFile] = File(...),
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> StudentRegisterResponse:
    db_path = request.app.state.db_path
    normalized_student_id = student_id.strip()
    normalized_name = name.strip()
    normalized_branch = branch.strip()
    normalized_batch = (batch.strip() or normalized_branch)

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one image")

    images_dir = Path(STUDENTS_DIR) / normalized_student_id
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    allowed_exts = {".jpg", ".jpeg", ".png"}
    uploaded_count = 0
    for index, upload in enumerate(images, start=1):
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in allowed_exts:
            suffix = ".jpg"
        image_bytes = await upload.read()
        if not image_bytes:
            continue
        output_path = images_dir / f"admin_{index:03d}{suffix}"
        output_path.write_bytes(image_bytes)
        uploaded_count += 1

    if uploaded_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid image content uploaded")

    upsert_student(student_id=normalized_student_id, name=normalized_name, db_path=db_path)
    upsert_student_profile(
        student_id=normalized_student_id,
        branch=normalized_branch,
        batch=normalized_batch,
        db_path=db_path,
    )

    try:
        valid_images = enroll_from_images(
            student_id=normalized_student_id,
            name=normalized_name,
            images_dir=images_dir,
            encodings_path=ENCODINGS_PATH,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enrollment failed: {exc}",
        ) from exc

    student = get_student_with_profile(student_id=normalized_student_id, db_path=db_path)
    if student is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Student save failed")

    return StudentRegisterResponse(
        ok=True,
        student=StudentResponse(**student),
        uploaded_images=uploaded_count,
        valid_images=valid_images,
    )
