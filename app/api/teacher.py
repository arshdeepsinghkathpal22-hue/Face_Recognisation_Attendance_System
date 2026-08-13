from datetime import datetime
import logging
from pathlib import Path
import re
import traceback

import cv2
import numpy as np
import face_recognition
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response

from app.api.schemas import (
    BatchesResponse,
    ClassSessionResponse,
    FrameDetectionResponse,
    FrameProcessResponse,
    SessionAttendanceResponse,
    SessionRosterItemResponse,
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
    TeacherSessionHistoryItemResponse,
)
from app.config import DATE_FMT, ENCODINGS_PATH, STUDENTS_DIR
from app.db import (
    create_class_session,
    get_class_session,
    get_session_student_roster,
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
    list_teacher_session_history,
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
_SESSION_FILTERED_CACHE: dict = {}
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


def _normalize_class_type(class_type: str, subject_id: str = "") -> str:
    if "LAB" in subject_id.upper() or "PRAC" in subject_id.upper():
        return "P"
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


def _get_session_known_faces(session_id: int, session_batch: str, db_path: str):
    known_faces = _get_known_faces()
    file_token = _KNOWN_FACES_CACHE.get("file_token")
    cache_key = (session_id, session_batch, file_token, db_path)

    if cache_key in _SESSION_FILTERED_CACHE:
        return _SESSION_FILTERED_CACHE[cache_key]

    filtered, load_debug = _filter_known_faces_for_session(
        known_faces=known_faces,
        session_batch=session_batch,
        db_path=db_path,
    )
    _SESSION_FILTERED_CACHE[cache_key] = (filtered, load_debug)
    return filtered, load_debug


def _invalidate_known_faces_cache() -> None:
    _KNOWN_FACES_CACHE["file_token"] = None
    _KNOWN_FACES_CACHE["data"] = None
    _SESSION_FILTERED_CACHE.clear()


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
    class_type = _normalize_class_type(payload.class_type, payload.subject_id)

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
        session_known_faces, load_debug = _get_session_known_faces(
            session_id=session_id,
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

    detected_face_count = len(recognition_results)

    # Scenario 1: No face detected in frame
    if detected_face_count == 0:
        stale_keys = [
            key for key in _RECOGNITION_STREAKS
            if key[0] == db_path and key[1] == session_id
        ]
        for key in stale_keys:
            _RECOGNITION_STREAKS.pop(key, None)

        detection_debug = {
            "detected_face_count": 0,
            "best_matched_student_id": None,
            "best_name": None,
            "best_euclidean_distance": 1.0,
            "configured_threshold": tolerance,
            "final_recognition_status": "no_face",
            "reason": "no_face_detected",
        }
        logger.info(
            "Recognition frame: session_id=%s detected_face_count=0 best_matched=None best_distance=1.0000 threshold=%.4f final_status=no_face",
            session_id,
            tolerance,
        )
        detection = FrameDetectionResponse(
            student_id="Unknown",
            name="Unknown",
            distance=1.0,
            status="no_face",
            warning="No face detected.",
            debug=detection_debug,
        )
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=[detection],
            present_students=present_students,
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": 0,
                "recognition_threshold": tolerance,
                **load_debug,
                "decisions": [detection_debug],
            },
        )

    # Scenario 2: Multiple faces detected in frame
    if detected_face_count > 1:
        stale_keys = [
            key for key in _RECOGNITION_STREAKS
            if key[0] == db_path and key[1] == session_id
        ]
        for key in stale_keys:
            _RECOGNITION_STREAKS.pop(key, None)

        min_distance = min((float(r.get("distance", 1.0)) for r in recognition_results), default=1.0)
        detection_debug = {
            "detected_face_count": detected_face_count,
            "best_matched_student_id": None,
            "best_name": None,
            "best_euclidean_distance": min_distance,
            "configured_threshold": tolerance,
            "final_recognition_status": "multiple_faces",
            "reason": "multiple_faces_detected",
        }
        logger.info(
            "Recognition frame: session_id=%s detected_face_count=%s best_matched=None best_distance=%.4f threshold=%.4f final_status=multiple_faces",
            session_id,
            detected_face_count,
            min_distance,
            tolerance,
        )
        detection = FrameDetectionResponse(
            student_id="Unknown",
            name="Unknown",
            distance=min_distance,
            status="multiple_faces",
            warning="Multiple faces detected. Please ensure only one registered student is visible.",
            debug=detection_debug,
        )
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=[detection],
            present_students=present_students,
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": detected_face_count,
                "recognition_threshold": tolerance,
                **load_debug,
                "decisions": [detection_debug],
            },
        )

    # Scenario 3: Single face detected
    result = recognition_results[0]
    best_student_id = result.get("best_student_id")
    best_name = result.get("best_name")
    best_distance = float(result.get("distance", 1.0))
    is_match = bool(result.get("matched", False))

    if not is_match:
        # FACE MISMATCH / UNKNOWN FACE
        stale_keys = [
            key for key in _RECOGNITION_STREAKS
            if key[0] == db_path and key[1] == session_id
        ]
        for key in stale_keys:
            _RECOGNITION_STREAKS.pop(key, None)

        detection_debug = {
            "detected_face_count": 1,
            "best_matched_student_id": best_student_id,
            "best_name": best_name,
            "best_euclidean_distance": best_distance,
            "configured_threshold": tolerance,
            "final_recognition_status": "face_mismatch",
            "reason": result.get("reason", "distance_above_threshold"),
        }
        logger.info(
            "Recognition frame: session_id=%s detected_face_count=1 best_matched=%s best_distance=%.4f threshold=%.4f final_status=face_mismatch",
            session_id,
            best_student_id,
            best_distance,
            tolerance,
        )
        detection = FrameDetectionResponse(
            student_id="Unknown",
            name="Unknown",
            distance=best_distance,
            status="face_mismatch",
            warning="Face does not match any registered student.",
            debug=detection_debug,
        )
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=[detection],
            present_students=present_students,
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": 1,
                "recognition_threshold": tolerance,
                **load_debug,
                "decisions": [detection_debug],
            },
        )

    # Scenario 4: Valid enrolled student face (distance <= tolerance)
    student_id = result["student_id"]
    student = get_student_with_profile(student_id=student_id, db_path=db_path)
    name = student["name"] if student else result["name"]

    # Clear confirmation streaks for any OTHER student for this session
    stale_keys = [
        key for key in _RECOGNITION_STREAKS
        if key[0] == db_path and key[1] == session_id and key[2] != student_id
    ]
    for key in stale_keys:
        _RECOGNITION_STREAKS.pop(key, None)

    # Check batch mismatch
    if not _is_student_in_selected_batch(
        student_id=student_id,
        student_batch=student["batch"] if student else "",
        session_batch=session["batch"],
        db_path=db_path,
    ):
        _RECOGNITION_STREAKS.pop((db_path, session_id, student_id), None)
        detection_debug = {
            "detected_face_count": 1,
            "best_matched_student_id": student_id,
            "best_name": name,
            "best_euclidean_distance": best_distance,
            "configured_threshold": tolerance,
            "final_recognition_status": "batch_mismatch",
            "reason": "batch_mismatch",
            "student_db_batch": student["batch"] if student else "",
            "active_session_batch": session["batch"],
        }
        logger.info(
            "Recognition frame: session_id=%s detected_face_count=1 best_matched=%s best_distance=%.4f threshold=%.4f final_status=batch_mismatch",
            session_id,
            student_id,
            best_distance,
            tolerance,
        )
        detection = FrameDetectionResponse(
            student_id=student_id,
            name=name,
            distance=best_distance,
            status="batch_mismatch",
            warning="Batch mismatch",
            debug=detection_debug,
        )
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=[detection],
            present_students=present_students,
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": 1,
                "recognition_threshold": tolerance,
                **load_debug,
                "decisions": [detection_debug],
            },
        )

    # Increment confirmation streak for this student
    streak_key = (db_path, session_id, student_id)
    streak_count = _RECOGNITION_STREAKS.get(streak_key, 0) + 1
    _RECOGNITION_STREAKS[streak_key] = streak_count

    detection_debug = {
        "detected_face_count": 1,
        "best_matched_student_id": student_id,
        "best_name": name,
        "best_euclidean_distance": best_distance,
        "configured_threshold": tolerance,
        "confirmation_streak": streak_count,
        "student_db_batch": student["batch"] if student else "",
        "active_session_batch": session["batch"],
    }

    if streak_count < REQUIRED_CONFIRMATION_FRAMES:
        detection_debug["final_recognition_status"] = "confirming"
        detection_debug["reason"] = "confirming"
        logger.info(
            "Recognition frame: session_id=%s detected_face_count=1 best_matched=%s best_distance=%.4f threshold=%.4f final_status=confirming streak=%s/%s",
            session_id,
            student_id,
            best_distance,
            tolerance,
            streak_count,
            REQUIRED_CONFIRMATION_FRAMES,
        )
        detection = FrameDetectionResponse(
            student_id=student_id,
            name=name,
            distance=best_distance,
            status="confirming",
            warning=f"Face recognized — confirming ({streak_count}/{REQUIRED_CONFIRMATION_FRAMES})...",
            debug=detection_debug,
        )
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=[detection],
            present_students=present_students,
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": 1,
                "recognition_threshold": tolerance,
                **load_debug,
                "decisions": [detection_debug],
            },
        )

    # Confirmation streak completed: mark attendance
    mark_result = mark_session_attendance(
        session_id=session_id,
        student_id=student_id,
        db_path=db_path,
    )
    if not mark_result["ok"]:
        detection_debug["final_recognition_status"] = mark_result["reason"]
        detection_debug["reason"] = mark_result["reason"]
        detection_debug["message"] = mark_result.get("message")
        warning = mark_result.get("message") or "Attendance was not marked."
        logger.info(
            "Recognition frame: session_id=%s detected_face_count=1 best_matched=%s best_distance=%.4f threshold=%.4f final_status=%s message=%s",
            session_id,
            student_id,
            best_distance,
            tolerance,
            mark_result["reason"],
            warning,
        )
        detection = FrameDetectionResponse(
            student_id=student_id,
            name=name,
            distance=best_distance,
            status=mark_result["reason"],
            warning=warning,
            debug=detection_debug,
        )
        present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
        return FrameProcessResponse(
            session_id=session_id,
            marked_in_frame=[detection],
            present_students=present_students,
            debug={
                "session_id": session_id,
                "selected_batch": session["batch"],
                "subject": session["subject_name"],
                "detected_face_count": 1,
                "recognition_threshold": tolerance,
                **load_debug,
                "decisions": [detection_debug],
            },
        )

    status_str = "registered"
    detection_debug["final_recognition_status"] = status_str
    detection_debug["reason"] = mark_result["reason"]
    detection_debug["attendance_inserted"] = mark_result["inserted"]
    warning = "Attendance marked successfully." if mark_result["inserted"] else "Attendance already marked."

    logger.info(
        "Attendance marked: session_id=%s detected_face_count=1 best_matched=%s best_distance=%.4f threshold=%.4f final_status=%s inserted=%s",
        session_id,
        student_id,
        best_distance,
        tolerance,
        status_str,
        mark_result["inserted"],
    )
    detection = FrameDetectionResponse(
        student_id=student_id,
        name=name,
        distance=best_distance,
        status=status_str,
        warning=warning,
        debug=detection_debug,
    )
    present_students = _get_present_students_payload(session_id=session_id, db_path=db_path)
    return FrameProcessResponse(
        session_id=session_id,
        marked_in_frame=[detection],
        present_students=present_students,
        debug={
            "session_id": session_id,
            "selected_batch": session["batch"],
            "subject": session["subject_name"],
            "detected_face_count": 1,
            "recognition_threshold": tolerance,
            **load_debug,
            "decisions": [detection_debug],
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


@router.get("/sessions/history", response_model=list[TeacherSessionHistoryItemResponse])
def get_teacher_sessions_history(
    request: Request,
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> list[TeacherSessionHistoryItemResponse]:
    history = list_teacher_session_history(teacher_id=teacher.teacher_id, db_path=request.app.state.db_path)
    return [TeacherSessionHistoryItemResponse(**item) for item in history]


@router.get("/sessions/{session_id}/roster", response_model=list[SessionRosterItemResponse])
def get_teacher_session_roster(
    session_id: int,
    request: Request,
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
) -> list[SessionRosterItemResponse]:
    session = _get_verified_teacher_session(session_id, teacher, request.app.state.db_path)
    roster = get_session_student_roster(session_id=session["id"], db_path=request.app.state.db_path)
    return [SessionRosterItemResponse(**item) for item in roster]


@router.get("/reports/csv")
def teacher_export_csv_report(
    request: Request,
    semester_id: str = "fall-2024",
    teacher: TeacherResponse = Depends(_get_authenticated_teacher),
):
    import csv
    import io
    db_path = request.app.state.db_path
    history = list_teacher_session_history(teacher_id=teacher.teacher_id, db_path=db_path)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Session ID", "Date", "Subject ID", "Subject Name", "Class Type", "Batch", "Present Count", "Marked Total"])

    for item in history:
        if item["semester_id"] == semester_id:
            writer.writerow([item["session_id"], item["session_date"], item["subject_id"], item["subject_name"], item["class_type"], item["batch"], item["present_students"], item["marked_students"]])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=teacher_sessions_{teacher.teacher_id}_{semester_id}.csv"},
    )

