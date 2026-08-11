from datetime import datetime
import logging
from pathlib import Path
import re
import traceback

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
    get_teacher_user_by_login,
    is_student_in_batch,
    is_teacher_assigned_to_class,
    list_active_semesters,
    list_batches,
    list_students,
    list_present_students_for_session,
    list_subjects_for_semester,
    list_teacher_assignments,
    mark_session_attendance,
    set_class_session_active,
    update_teacher_password,
)
from app.face_utils import EnrollmentValidationError, load_known_faces, recognize_in_frame
from app.security import hash_password, password_needs_rehash, verify_password
from app.services.enrollment_service import enroll_student_uploads

router = APIRouter(prefix="/api/teacher", tags=["teacher"])
logger = logging.getLogger(__name__)

_KNOWN_FACES_CACHE: dict = {"file_token": None, "data": None}
_RECOGNITION_STREAKS: dict[tuple[str, int, str], int] = {}
REQUIRED_CONFIRMATION_FRAMES = 2


def _get_authenticated_teacher(request: Request) -> TeacherResponse:
    teacher_id = request.session.get("teacher_id")
    if not teacher_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    teacher = get_teacher_user(teacher_id=teacher_id, db_path=request.app.state.db_path)
    if teacher is None:
        request.session.pop("teacher_id", None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return TeacherResponse(
        teacher_id=teacher["teacher_id"],
        name=teacher["name"],
        email=teacher.get("email") or "",
    )


def _normalize_class_type(class_type: str) -> str:
    normalized = class_type.upper().strip()
    if normalized not in {"L", "T", "P"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="class_type must be L, T, or P")
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
    db_path = _KNOWN_FACES_CACHE.get("db_path")
    if (
        _KNOWN_FACES_CACHE["data"] is None
        or _KNOWN_FACES_CACHE["file_token"] != file_token
        or db_path != _KNOWN_FACES_CACHE.get("active_db_path")
    ):
        known_faces = load_known_faces(encodings_path)
        student_names = {
            student["student_id"]: student["name"]
            for student in list_students(db_path=db_path)
        } if db_path else {}
        indexes = [
            index
            for index, student_id in enumerate(known_faces["student_ids"])
            if student_id in student_names
        ]
        known_faces = {
            "student_ids": [known_faces["student_ids"][index] for index in indexes],
            "names": [
                student_names[known_faces["student_ids"][index]]
                for index in indexes
            ],
            "encodings": [known_faces["encodings"][index] for index in indexes],
        }
        _KNOWN_FACES_CACHE["data"] = known_faces
        _KNOWN_FACES_CACHE["file_token"] = file_token
        _KNOWN_FACES_CACHE["active_db_path"] = db_path
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
    if not is_teacher_assigned_to_class(
        teacher_id=teacher.teacher_id,
        semester_id=session["semester_id"],
        subject_id=session["subject_id"],
        batch=session["batch"],
        class_type=session["class_type"],
        db_path=db_path,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Class is not assigned to this teacher")
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


def _batch_parts(value: str | None) -> set[str]:
    normalized = _normalize_batch_label(value)
    if not normalized:
        return set()
    return {part for part in re.split(r"[-_/]+", normalized) if part}


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

    normalized_student_batch = _normalize_batch_label(student_batch)
    if normalized_student_batch == normalized_session_batch:
        return True

    # Support compact multi-batch notation used by teachers, e.g. "F5F6".
    session_f_batches = _extract_f_batches(normalized_session_batch)
    if len(session_f_batches) >= 2:
        student_f_batches = set(_extract_f_batches(normalized_student_batch))
        return bool(student_f_batches.intersection(session_f_batches))

    student_parts = _batch_parts(normalized_student_batch)
    session_parts = _batch_parts(normalized_session_batch)
    if student_parts and session_parts:
        if normalized_session_batch in student_parts:
            return True
        if normalized_student_batch in session_parts:
            return True
        if student_parts.intersection(session_parts) and not _extract_f_batches(normalized_session_batch):
            return True
        session_f_batch = set(_extract_f_batches(normalized_session_batch))
        student_f_batch = set(_extract_f_batches(normalized_student_batch))
        if session_f_batch and student_f_batch and session_f_batch.intersection(student_f_batch):
            return True

    return is_student_in_batch(student_id, session_batch or "", db_path=db_path)


def _encoding_count_by_student(known_faces: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for student_id in known_faces.get("student_ids", []):
        normalized_student_id = str(student_id)
        counts[normalized_student_id] = counts.get(normalized_student_id, 0) + 1
    return counts


def _filter_known_faces_for_session(
    known_faces: dict,
    session_batch: str,
    db_path: str,
) -> tuple[dict, dict]:
    students = {
        student["student_id"]: student
        for student in list_students(db_path=db_path)
    }
    loaded_indexes: list[int] = []
    skipped: list[dict] = []
    student_ids = known_faces.get("student_ids", [])
    names = known_faces.get("names", [])
    encodings = known_faces.get("encodings", [])
    size = min(len(student_ids), len(names), len(encodings))

    for index in range(size):
        student_id = str(student_ids[index])
        student = students.get(student_id)
        if student is None:
            skipped.append(
                {
                    "student_id": student_id,
                    "reason": "encoding_student_id_missing_in_db",
                }
            )
            continue
        if not _is_student_in_selected_batch(
            student_id=student_id,
            student_batch=student.get("batch", ""),
            session_batch=session_batch,
            db_path=db_path,
        ):
            skipped.append(
                {
                    "student_id": student_id,
                    "student_batch": student.get("batch", ""),
                    "session_batch": session_batch,
                    "reason": "not_in_session_batch",
                }
            )
            continue
        loaded_indexes.append(index)

    filtered = {
        "student_ids": [str(student_ids[index]) for index in loaded_indexes],
        "names": [
            students.get(str(student_ids[index]), {}).get("name") or str(names[index])
            for index in loaded_indexes
        ],
        "encodings": [encodings[index] for index in loaded_indexes],
    }
    debug = {
        "loaded_student_ids": sorted(set(filtered["student_ids"])),
        "loaded_encoding_count": len(filtered["encodings"]),
        "encoding_counts_by_student": _encoding_count_by_student(filtered),
        "skipped_encodings": skipped,
    }
    return filtered, debug


@router.post("/auth/login", response_model=TeacherLoginResponse)
def teacher_login(payload: TeacherLoginRequest, request: Request) -> TeacherLoginResponse:
    teacher = get_teacher_user_by_login(login=payload.teacher_id, db_path=request.app.state.db_path)
    if teacher is None or not verify_password(payload.password, teacher["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid teacher credentials")
    if password_needs_rehash(teacher["password"]):
        update_teacher_password(
            teacher["teacher_id"],
            hash_password(payload.password),
            db_path=request.app.state.db_path,
        )

    request.session["teacher_id"] = teacher["teacher_id"]
    request.session.pop("student_id", None)
    request.session.pop("admin_id", None)
    return TeacherLoginResponse(
        ok=True,
        teacher=TeacherResponse(
            teacher_id=teacher["teacher_id"],
            name=teacher["name"],
            email=teacher.get("email") or "",
        ),
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
        teacher=TeacherResponse(
            teacher_id=teacher["teacher_id"],
            name=teacher["name"],
            email=teacher.get("email") or "",
        ),
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
    if not is_teacher_assigned_to_class(
        teacher_id=teacher.teacher_id,
        semester_id=payload.semester_id,
        subject_id=payload.subject_id,
        batch=payload.batch,
        class_type=class_type,
        db_path=db_path,
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
    logger.info(
        "Attendance session started: session_id=%s selected_batch=%s subject=%s teacher_id=%s",
        session["id"],
        session["batch"],
        session["subject_name"],
        teacher.teacher_id,
    )
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
    _KNOWN_FACES_CACHE["db_path"] = db_path
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
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": len(detections),
                "mode": "detect",
            },
        )

    try:
        known_faces = _get_known_faces()
        session_known_faces, load_debug = _filter_known_faces_for_session(
            known_faces=known_faces,
            session_batch=session["batch"],
            db_path=db_path,
        )
        logger.info(
            "Recognition load for session_id=%s selected_batch=%s subject=%s loaded_student_ids=%s loaded_encoding_count=%s",
            session_id,
            session["batch"],
            session["subject_name"],
            load_debug["loaded_student_ids"],
            load_debug["loaded_encoding_count"],
        )
        recognition_results = recognize_in_frame(decoded, session_known_faces, tolerance=tolerance)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Recognition failed for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Recognition failed: {exc}",
                "trace": traceback.format_exc(limit=5),
            },
        ) from exc

    marked_by_student: dict[str, FrameDetectionResponse] = {}
    seen_student_ids: set[str] = set()
    decision_debug: list[dict] = []
    for result in recognition_results:
        result_debug = {
            "detected": True,
            "best_matched_student_id": result.get("best_student_id") or result.get("student_id"),
            "best_euclidean_distance": float(result.get("distance", 1.0)),
            "recognition_threshold": tolerance,
            "active_session_batch": session["batch"],
            "reason": result.get("reason", "unknown"),
        }
        if not result.get("matched"):
            result_debug["reason"] = result.get("reason", "distance_above_threshold")
            decision_debug.append(result_debug)
            continue

        student_id = result["student_id"]
        seen_student_ids.add(student_id)
        student = get_student_with_profile(student_id=student_id, db_path=db_path)
        name = student["name"] if student else result["name"]
        result_debug["student_db_batch"] = student["batch"] if student else ""
        result_debug["student_name"] = name

        if not _is_student_in_selected_batch(
            student_id=student_id,
            student_batch=student["batch"] if student else "",
            session_batch=session["batch"],
            db_path=db_path,
        ):
            result_debug["reason"] = "batch_mismatch"
            decision_debug.append(result_debug)
            logger.info(
                "Recognition rejected: session_id=%s student_id=%s distance=%.4f threshold=%.4f student_batch=%s session_batch=%s reason=batch_mismatch",
                session_id,
                student_id,
                float(result["distance"]),
                tolerance,
                student["batch"] if student else "",
                session["batch"],
            )
            detection = FrameDetectionResponse(
                student_id=student_id,
                name=name,
                distance=float(result["distance"]),
                status="batch_mismatch",
                warning="Batch mismatch",
                debug=result_debug,
            )
            previous = marked_by_student.get(student_id)
            if previous is None or detection.distance < previous.distance:
                marked_by_student[student_id] = detection
            continue

        streak_key = (db_path, session_id, student_id)
        streak_count = _RECOGNITION_STREAKS.get(streak_key, 0) + 1
        _RECOGNITION_STREAKS[streak_key] = streak_count
        result_debug["confirmation_streak"] = streak_count
        if streak_count < REQUIRED_CONFIRMATION_FRAMES:
            result_debug["reason"] = "confirming"
            decision_debug.append(result_debug)
            detection = FrameDetectionResponse(
                student_id=student_id,
                name=name,
                distance=float(result["distance"]),
                status="confirming",
                warning=f"Confirming {streak_count}/{REQUIRED_CONFIRMATION_FRAMES}",
                debug=result_debug,
            )
            previous = marked_by_student.get(student_id)
            if previous is None or detection.distance < previous.distance:
                marked_by_student[student_id] = detection
            continue

        mark_result = mark_session_attendance(
            session_id=session_id,
            student_id=student_id,
            db_path=db_path,
        )
        if not mark_result["ok"]:
            result_debug["reason"] = mark_result["reason"]
            result_debug["message"] = mark_result.get("message")
            decision_debug.append(result_debug)
            warning = mark_result.get("message") or "Attendance was not marked."
            detection = FrameDetectionResponse(
                student_id=student_id,
                name=name,
                distance=float(result["distance"]),
                status=mark_result["reason"],
                warning=warning,
                debug=result_debug,
            )
            previous = marked_by_student.get(student_id)
            if previous is None or detection.distance < previous.distance:
                marked_by_student[student_id] = detection
            continue

        result_debug["reason"] = mark_result["reason"]
        result_debug["attendance_inserted"] = mark_result["inserted"]
        decision_debug.append(result_debug)
        logger.info(
            "Attendance marked: session_id=%s student_id=%s name=%s distance=%.4f threshold=%.4f batch=%s inserted=%s",
            session_id,
            student_id,
            name,
            float(result["distance"]),
            tolerance,
            student["batch"] if student else "",
            mark_result["inserted"],
        )
        detection = FrameDetectionResponse(
            student_id=student_id,
            name=name,
            distance=float(result["distance"]),
            status="registered",
            debug=result_debug,
        )

        # Keep the best (lowest distance) detection for each student in this frame.
        previous = marked_by_student.get(student_id)
        if previous is None or detection.distance < previous.distance:
            marked_by_student[student_id] = detection

    stale_keys = [
        key
        for key in _RECOGNITION_STREAKS
        if key[0] == db_path and key[1] == session_id and key[2] not in seen_student_ids
    ]
    for key in stale_keys:
        _RECOGNITION_STREAKS.pop(key, None)

    present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
    return FrameProcessResponse(
        session_id=session_id,
        marked_in_frame=list(marked_by_student.values()),
        present_students=present_students,
        debug={
            "session_id": session_id,
            "selected_batch": session["batch"],
            "subject": session["subject_name"],
            "detected_face_count": len(recognition_results),
            "recognition_threshold": tolerance,
            **load_debug,
            "decisions": decision_debug,
        },
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload/capture 5-15 face images")

    try:
        enrollment = await enroll_student_uploads(
            student_id=normalized_student_id,
            name=normalized_name,
            branch=normalized_branch,
            batch=normalized_batch,
            images=images,
            db_path=db_path,
            encodings_path=ENCODINGS_PATH,
            students_dir=STUDENTS_DIR,
            filename_prefix="web",
        )
    except EnrollmentValidationError as exc:
        detail = {"message": str(exc), "results": exc.results}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enrollment failed: {exc}",
        ) from exc

    _invalidate_known_faces_cache()
    return StudentRegisterResponse(
        ok=True,
        student=StudentResponse(**enrollment["student"]),
        uploaded_images=enrollment["uploaded_images"],
        valid_images=enrollment["valid_images"],
        rejected_images=enrollment["rejected_images"],
        results=enrollment["results"],
    )
