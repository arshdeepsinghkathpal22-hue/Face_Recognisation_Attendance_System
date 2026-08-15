from pathlib import Path
import logging
import shutil

from fastapi import UploadFile

from app.config import ENCODINGS_PATH, STUDENTS_DIR
from app.db import get_student_with_profile, upsert_student, upsert_student_profile
from app.face_utils import (
    EnrollmentValidationError,
    MAX_ENROLLMENT_IMAGES,
    MIN_ENROLLMENT_IMAGES,
    extract_enrollment_encoding,
    save_student_encodings,
)

logger = logging.getLogger(__name__)


async def enroll_student_uploads(
    *,
    student_id: str,
    name: str,
    branch: str,
    batch: str,
    images: list[UploadFile],
    db_path: str,
    encodings_path: str | Path | None = None,
    students_dir: str | Path | None = None,
    filename_prefix: str = "enroll",
) -> dict:
    if encodings_path is None:
        encodings_path = ENCODINGS_PATH
    if students_dir is None:
        students_dir = STUDENTS_DIR

    normalized_student_id = student_id.strip()
    normalized_name = name.strip()
    normalized_branch = branch.strip()
    normalized_batch = (batch.strip() or normalized_branch)

    if not normalized_student_id or not normalized_name or not normalized_branch:
        raise EnrollmentValidationError("Student ID, name, and branch are required")
    if len(images) < MIN_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Upload/capture {MIN_ENROLLMENT_IMAGES}-{MAX_ENROLLMENT_IMAGES} face images"
        )
    if len(images) > MAX_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Enrollment allows at most {MAX_ENROLLMENT_IMAGES} images"
        )

    allowed_exts = {".jpg", ".jpeg", ".png"}
    accepted: list[tuple[str, bytes]] = []
    encodings = []
    results: list[dict] = []

    for index, upload in enumerate(images, start=1):
        original_name = upload.filename or f"image-{index}.jpg"
        suffix = Path(original_name).suffix.lower()
        if suffix not in allowed_exts:
            suffix = ".jpg"

        image_bytes = await upload.read()
        if not image_bytes:
            results.append(
                {
                    "filename": original_name,
                    "accepted": False,
                    "message": "Empty image file",
                }
            )
            continue

        encoding, msg_or_error = extract_enrollment_encoding(image_bytes)
        accepted_status = encoding is not None
        if not accepted_status or encoding is None:
            results.append(
                {
                    "filename": original_name,
                    "accepted": False,
                    "message": msg_or_error or "Face encoding failed",
                }
            )
            continue

        stored_name = f"{filename_prefix}_{len(accepted) + 1:03d}{suffix}"
        accepted.append((stored_name, image_bytes))
        encodings.append(encoding)
        results.append(
            {
                "filename": original_name,
                "accepted": True,
                "message": msg_or_error or "Accepted",
            }
        )

    if len(encodings) < MIN_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Enrollment requires at least {MIN_ENROLLMENT_IMAGES} valid face images",
            results=results,
        )
    if len(encodings) > MAX_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Enrollment allows at most {MAX_ENROLLMENT_IMAGES} valid face images",
            results=results,
        )

    images_dir = Path(students_dir) / normalized_student_id
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    for filename, image_bytes in accepted:
        (images_dir / filename).write_bytes(image_bytes)

    upsert_student(student_id=normalized_student_id, name=normalized_name, db_path=db_path)
    upsert_student_profile(
        student_id=normalized_student_id,
        branch=normalized_branch,
        batch=normalized_batch,
        db_path=db_path,
    )
    save_student_encodings(
        student_id=normalized_student_id,
        name=normalized_name,
        encodings=encodings,
        encodings_path=encodings_path,
    )

    student = get_student_with_profile(student_id=normalized_student_id, db_path=db_path)
    if student is None:
        raise RuntimeError(f"Database student profile save failed for {normalized_student_id}")

    # Explicit Verification of Encodings on Disk
    from app.face_utils import load_known_faces
    persisted = load_known_faces(encodings_path)
    persisted_sids = [str(sid).strip() for sid in persisted.get("student_ids", [])]
    persisted_count = persisted_sids.count(normalized_student_id)
    if persisted_count != len(encodings):
        raise RuntimeError(
            f"Registration aborted: Encodings not persisted correctly. "
            f"Expected {len(encodings)} embeddings for {normalized_student_id}, found {persisted_count} in {encodings_path}"
        )

    # Invalidate cache so attendance session immediately loads new encodings
    try:
        from app.api.teacher import _invalidate_known_faces_cache
        _invalidate_known_faces_cache()
    except Exception:
        pass

    logger.info(
        "ENROLLMENT_VERIFIED: student_id=%s student_name=%s student_batch=%s valid_photos=%d embeddings_count=%d embedding_dim=128 storage_path=%s persisted=True",
        student["student_id"],
        student["name"],
        student["batch"],
        len(accepted),
        len(encodings),
        str(encodings_path),
    )

    return {
        "student": student,
        "uploaded_images": len(images),
        "valid_images": len(encodings),
        "rejected_images": len(images) - len(encodings),
        "results": results,
    }
