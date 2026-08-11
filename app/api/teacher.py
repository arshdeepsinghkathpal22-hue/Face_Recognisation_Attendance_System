from datetime import datetime
from pathlib import Path
import re
import shutil

import cv2
import numpy as np
import face_recognition
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from app.api.schemas import (
    BatchesResponse,
    ClassSessionResponse,
    FrameDetectionResponse,
    FrameProcessResponse,
    SessionAttendanceResponse,
    StartClassSessionRequest,
    StudentRegisterResponse,
    StudentResponse,
    SubjectListResponse,
    TeacherAssignmentResponse,
    TeacherAssignmentsResponse,
    TeacherLoginRequest,
    TeacherLoginResponse,
    TeacherMeResponse,
    TeacherResponse,
)
from app.config import DATE_FMT, ENCODINGS_PATH, STUDENTS_DIR
from app.db import (
    create_class_session,
    get_class_session,
    get_student_with_profile,
    get_teacher_user,
    is_student_in_batch,
    list_active_semesters,
    list_batches,
    list_present_students_for_session,
    list_subjects_for_semester,
    list_teacher_assignments,
    set_class_session_active,
    upsert_student,
    upsert_student_profile,
    upsert_session_attendance,
)
from app.face_utils import enroll_from_images, load_known_faces, recognize_in_frame

router = APIRouter(prefix="/api/teacher", tags=["teacher"])

_KNOWN_FACES_CACHE: dict = {"file_token": None, "data": None}


def _get_authenticated_teacher(request: Request) -> TeacherResponse:
    teacher_id = request.session.get("teacher_id")
    if not teacher_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    teacher = get_teacher_user(teacher_id=teacher_id, db_path=request.app.state.db_path)
    if teacher is None:
        request.session.pop("teacher_id", None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return TeacherResponse(teacher_id=teacher["teacher_id"], name=teacher["name"])


def _normalize_class_type(class_type: str) -> str:
    normalized = class_type.upper().strip()
    if normalized not in {"L", "P"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="class_type must be L or P")
    return normalized


def _session_response(session: dict) -> ClassSessionResponse:
    return ClassSessionResponse(
        session_id=session["id"],
        batch=session["batch"],
        semester_id=session["semester_id"],
        subject_id=session["subject_id"],
        subject_name=session["subject_name"],
        class_type=session["class_type"],
        session_date=session["session_date"],
        start_time=session["start_time"],
        end_time=session["end_time"],
        is_active=bool(session["is_active"]),
    )


def _get_known_faces():
    encodings_path = Path(ENCODINGS_PATH)
    if not encodings_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face encodings found. Run enrollment first.",
        )

    stat = encodings_path.stat()
    file_token = (stat.st_mtime_ns, stat.st_size)
    if _KNOWN_FACES_CACHE["data"] is None or _KNOWN_FACES_CACHE["file_token"] != file_token:
        _KNOWN_FACES_CACHE["data"] = load_known_faces(encodings_path)
        _KNOWN_FACES_CACHE["file_token"] = file_token
    return _KNOWN_FACES_CACHE["data"]


def _invalidate_known_faces_cache() -> None:
    _KNOWN_FACES_CACHE["file_token"] = None
    _KNOWN_FACES_CACHE["data"] = None


def _get_verified_teacher_session(
    session_id: int,
    teacher: TeacherResponse,
    db_path: str,
) -> dict:
    session = get_class_session(session_id=session_id, db_path=db_path)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["teacher_id"] != teacher.teacher_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session not owned by teacher")
    return session


def _get_present_students_payload(session_id: int, db_path: str) -> list[StudentResponse]:
    present_rows = list_present_students_for_session(session_id=session_id, db_path=db_path)
    payload: list[StudentResponse] = []
    for row in present_rows:
        student = get_student_with_profile(student_id=row["student_id"], db_path=db_path)
        if student:
            payload.append(StudentResponse(**student))
        else:
            payload.append(StudentResponse(student_id=row["student_id"], name=row["name"]))
    return payload


def _normalize_batch_label(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def _extract_f_batches(value: str | None) -> list[str]:
    normalized = _normalize_batch_label(value)
    if not normalized:
        return []
    return re.findall(r"F\d{1,2}", normalized)


def _is_student_in_selected_batch(
    student_id: str,
    student_batch: str | None,
    session_batch: str | None,
    db_path: str,
) -> bool:
    normalized_session_batch = _normalize_batch_label(session_batch)
    if not normalized_session_batch:
        return True

    # Support compact multi-batch notation used by teachers, e.g. "F5F6".
    session_f_batches = _extract_f_batches(normalized_session_batch)
    if len(session_f_batches) >= 2:
        normalized_student_batch = _normalize_batch_label(student_batch)
        return normalized_student_batch in set(session_f_batches)

    normalized_student_batch = _normalize_batch_label(student_batch)
    if normalized_student_batch:
        return normalized_student_batch == normalized_session_batch

    return is_student_in_batch(student_id, session_batch or "", db_path=db_path)


@router.post("/auth/login", response_model=TeacherLoginResponse)
def teacher_login(payload: TeacherLoginRequest, request: Request) -> TeacherLoginResponse:
    teacher = get_teacher_user(teacher_id=payload.teacher_id, db_path=request.app.state.db_path)
    if teacher is None or teacher["password"] != payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid teacher credentials")

    request.session["teacher_id"] = payload.teacher_id
    request.session.pop("student_id", None)
    request.session.pop("admin_id", None)
    return TeacherLoginResponse(
        ok=True,
        teacher=TeacherResponse(teacher_id=teacher["teacher_id"], name=teacher["name"]),
    )


@router.post("/auth/logout")
def teacher_logout(request: Request) -> dict:
    request.session.pop("teacher_id", None)
    return {"ok": True}


@router.get("/me", response_model=TeacherMeResponse)
def teacher_me(request: Request) -> TeacherMeResponse:
    teacher_id = request.session.get("teacher_id")
    if not teacher_id:
        return TeacherMeResponse(logged_in=False, teacher=None)

    teacher = get_teacher_user(teacher_id=teacher_id, db_path=request.app.state.db_path)
    if teacher is None:
        request.session.pop("teacher_id", None)
        return TeacherMeResponse(logged_in=False, teacher=None)

    return TeacherMeResponse(
        logged_in=True,
        teacher=TeacherResponse(teacher_id=teacher["teacher_id"], name=teacher["name"]),
    )


@router.get("/semesters")
def teacher_semesters(
    request: Request,
    _: TeacherResponse = Depends(_get_authenticated_teacher),
) -> dict:
    return {"items": list_active_semesters(db_path=request.app.state.db_path)}


@router.get("/batches", response_model=BatchesResponse)
def teacher_batches(
    request: Request,
    _: TeacherResponse = Depends(_get_authenticated_teacher),
) -> BatchesResponse:
    return BatchesResponse(items=list_batches(db_path=request.app.state.db_path))


@router.get("/subjects", response_model=SubjectListResponse)
def teacher_subjects(
    request: Request,
    semester_id: str = Query(..., min_length=1),
    _: TeacherResponse = Depends(_get_authenticated_teacher),
) -> SubjectListResponse:
    return SubjectListResponse(
        items=list_subjects_for_semester(semester_id=semester_id, db_path=request.app.state.db_path)
    )


@router.get("/assignments", response_model=TeacherAssignmentsResponse)
def teacher_assignments(
    request: Request,
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> TeacherAssignmentsResponse:
    rows = list_teacher_assignments(teacher_id=teacher.teacher_id, db_path=request.app.state.db_path)
    return TeacherAssignmentsResponse(items=[TeacherAssignmentResponse(**row) for row in rows])


@router.post("/sessions/start", response_model=ClassSessionResponse)
def start_teacher_session(
    payload: StartClassSessionRequest,
    request: Request,
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> ClassSessionResponse:
    db_path = request.app.state.db_path
    class_type = _normalize_class_type(payload.class_type)

    subjects = list_subjects_for_semester(payload.semester_id, db_path=db_path)
    if not any(subject["id"] == payload.subject_id for subject in subjects):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject does not belong to semester")
    assignments = list_teacher_assignments(teacher_id=teacher.teacher_id, db_path=db_path)
    if not any(
        assignment["semester_id"] == payload.semester_id
        and assignment["subject_id"] == payload.subject_id
        and assignment["batch"] == payload.batch
        and assignment["class_type"] == class_type
        for assignment in assignments
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Class is not assigned to this teacher")

    session_id = create_class_session(
        subject_id=payload.subject_id,
        semester_id=payload.semester_id,
        class_type=class_type,
        session_date=datetime.now().strftime(DATE_FMT),
        batch=payload.batch,
        start_time=payload.start_time,
        end_time=payload.end_time,
        teacher_id=teacher.teacher_id,
        db_path=db_path,
    )
    session = get_class_session(session_id=session_id, db_path=db_path)
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create session")
    return _session_response(session)


@router.post("/sessions/{session_id}/stop", response_model=ClassSessionResponse)
def stop_teacher_session(
    session_id: int,
    request: Request,
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> ClassSessionResponse:
    db_path = request.app.state.db_path
    _get_verified_teacher_session(session_id=session_id, teacher=teacher, db_path=db_path)
    set_class_session_active(session_id=session_id, is_active=False, db_path=db_path)
    updated = get_class_session(session_id=session_id, db_path=db_path)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _session_response(updated)


@router.post("/sessions/{session_id}/frame", response_model=FrameProcessResponse)
async def process_teacher_frame(
    session_id: int,
    request: Request,
    frame: UploadFile = File(...),
    tolerance: float = Form(0.6),
    mode: str = Form("recognize"),
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> FrameProcessResponse:
    db_path = request.app.state.db_path
    session = _get_verified_teacher_session(session_id=session_id, teacher=teacher, db_path=db_path)
    if not bool(session["is_active"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active")

    image_bytes = await frame.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty frame received")

    nparr = np.frombuffer(image_bytes, np.uint8)
    decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image frame")

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"detect", "recognize"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be detect or recognize")
    if tolerance < 0.3 or tolerance > 0.8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tolerance must be between 0.3 and 0.8")

    if normalized_mode == "detect":
        frame_rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        frame_rgb = np.ascontiguousarray(frame_rgb)
        face_locations = face_recognition.face_locations(frame_rgb, model="hog")
        detections = [
            FrameDetectionResponse(
                student_id=f"detected-{index + 1}",
                name=f"Face {index + 1}",
                distance=0.0,
            )
            for index, _ in enumerate(face_locations)
        ]
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=detections,
            present_students=present_students,
        )

    known_faces = _get_known_faces()
    try:
        recognition_results = recognize_in_frame(decoded, known_faces, tolerance=tolerance)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recognition failed: {exc}",
        ) from exc

    marked_by_student: dict[str, FrameDetectionResponse] = {}
    for result in recognition_results:
        if not result.get("matched"):
            continue

        student_id = result["student_id"]
        student = get_student_with_profile(student_id=student_id, db_path=db_path)
        name = student["name"] if student else result["name"]

        if not _is_student_in_selected_batch(
            student_id=student_id,
            student_batch=student["batch"] if student else "",
            session_batch=session["batch"],
            db_path=db_path,
        ):
            detection = FrameDetectionResponse(
                student_id=student_id,
                name=name,
                distance=float(result["distance"]),
                status="batch_mismatch",
                warning="Batch mismatch",
            )
            previous = marked_by_student.get(student_id)
            if previous is None or detection.distance < previous.distance:
                marked_by_student[student_id] = detection
            continue

        upsert_session_attendance(
            session_id=session_id,
            student_id=student_id,
            present=1,
            db_path=db_path,
        )

        detection = FrameDetectionResponse(
            student_id=student_id,
            name=name,
            distance=float(result["distance"]),
            status="registered",
        )

        # Keep the best (lowest distance) detection for each student in this frame.
        previous = marked_by_student.get(student_id)
        if previous is None or detection.distance < previous.distance:
            marked_by_student[student_id] = detection

    present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
    return FrameProcessResponse(
        session_id=session_id,
        marked_in_frame=list(marked_by_student.values()),
        present_students=present_students,
    )


@router.get("/sessions/{session_id}/attendance", response_model=SessionAttendanceResponse)
def teacher_session_attendance(
    session_id: int,
    request: Request,
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> SessionAttendanceResponse:
    db_path = request.app.state.db_path
    _get_verified_teacher_session(session_id=session_id, teacher=teacher, db_path=db_path)
    return SessionAttendanceResponse(
        session_id=session_id,
        present_students=_get_present_students_payload(session_id=session_id, db_path=db_path),
    )


@router.post("/students/register", response_model=StudentRegisterResponse)
async def register_student_via_teacher(
    request: Request,
    student_id: str = Form(..., min_length=1),
    name: str = Form(..., min_length=1),
    branch: str = Form(..., min_length=1),
    batch: str = Form(""),
    images: list[UploadFile] = File(...),
    _: TeacherResponse = Depends(_get_authenticated_teacher),
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
        output_path = images_dir / f"web_{index:03d}{suffix}"
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

    _invalidate_known_faces_cache()
    student = get_student_with_profile(student_id=normalized_student_id, db_path=db_path)
    if student is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Student save failed")

    return StudentRegisterResponse(
        ok=True,
        student=StudentResponse(**student),
        uploaded_images=uploaded_count,
        valid_images=valid_images,
    )
