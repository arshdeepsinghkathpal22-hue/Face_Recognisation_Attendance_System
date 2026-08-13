import pickle
import tempfile
from pathlib import Path

import face_recognition
import cv2
import numpy as np

from app.config import ENCODINGS_PATH

KnownFaces = dict[str, list]
EMBEDDING_SIZE = 128
MIN_ENROLLMENT_IMAGES = 5
MAX_ENROLLMENT_IMAGES = 15


class EnrollmentValidationError(RuntimeError):
    def __init__(self, message: str, results: list[dict] | None = None):
        super().__init__(message)
        self.results = results or []


def _empty_known_faces() -> KnownFaces:
    return {"student_ids": [], "names": [], "encodings": []}


def _normalize_encoding(encoding) -> np.ndarray | None:
    try:
        array = np.asarray(encoding, dtype=np.float64).reshape(-1)
    except Exception:
        return None
    if array.shape[0] != EMBEDDING_SIZE:
        return None
    return array


def _sanitize_known_faces(known_faces: dict) -> KnownFaces:
    student_ids = known_faces.get("student_ids", [])
    names = known_faces.get("names", [])
    encodings = known_faces.get("encodings", [])
    size = min(len(student_ids), len(names), len(encodings))

    sanitized = _empty_known_faces()
    for index in range(size):
        normalized = _normalize_encoding(encodings[index])
        if normalized is None:
            continue
        sanitized["student_ids"].append(str(student_ids[index]))
        sanitized["names"].append(str(names[index]))
        sanitized["encodings"].append(normalized)
    return sanitized


def load_known_faces(encodings_path: str | Path = ENCODINGS_PATH) -> KnownFaces:
    path = Path(encodings_path)
    if not path.exists():
        return _empty_known_faces()
    try:
        with path.open("rb") as file:
            data = pickle.load(file)
    except Exception:
        return _empty_known_faces()
    return _sanitize_known_faces(data if isinstance(data, dict) else {})


def save_known_faces(
    known_faces: KnownFaces,
    encodings_path: str | Path = ENCODINGS_PATH,
) -> None:
    path = Path(encodings_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = _sanitize_known_faces(known_faces)

    # Atomic write avoids corrupted pickle reads while scanning frames.
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent) as tmp:
        pickle.dump(sanitized, tmp)
        temp_name = tmp.name
    Path(temp_name).replace(path)


def _quality_issue(image_rgb: np.ndarray) -> str | None:
    height, width = image_rgb.shape[:2]
    if height < 120 or width < 120:
        return "Image is too small"

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    brightness = float(np.mean(gray))
    if brightness < 15:
        return "Image is too dark"
    if brightness > 240:
        return "Image is too bright"

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < 12:
        return "Image is too blurry"
    return None


def enhance_low_light_image(image_rgb: np.ndarray) -> np.ndarray:
    """Enhance low-light/dark images using CLAHE on LAB color space + gamma correction."""
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)

    enhanced_lab = cv2.merge((cl, a, b))
    enhanced_rgb = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)

    inv_gamma = 1.0 / 1.4
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(enhanced_rgb, table)


def extract_enrollment_encoding(image_bytes: bytes) -> tuple[np.ndarray | None, str | None]:
    nparr = np.frombuffer(image_bytes, np.uint8)
    decoded_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if decoded_bgr is None:
        return None, "Invalid image file"

    image_rgb = cv2.cvtColor(decoded_bgr, cv2.COLOR_BGR2RGB)
    image_rgb = np.ascontiguousarray(image_rgb)
    quality_issue = _quality_issue(image_rgb)
    if quality_issue:
        return None, quality_issue

    locations = face_recognition.face_locations(image_rgb, model="hog")
    enhanced_used = False

    # Retry with low-light enhancement if no face detected or dark image
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    brightness = float(np.mean(gray))
    if len(locations) == 0 or brightness < 65:
        enhanced_rgb = enhance_low_light_image(image_rgb)
        enhanced_locations = face_recognition.face_locations(enhanced_rgb, model="hog")
        if len(enhanced_locations) == 1 and len(locations) == 0:
            image_rgb = enhanced_rgb
            locations = enhanced_locations
            enhanced_used = True

    if len(locations) == 0:
        locations = face_recognition.face_locations(
            image_rgb,
            number_of_times_to_upsample=1,
            model="hog",
        )
    if len(locations) == 0:
        return None, "No face found"
    if len(locations) > 1:
        return None, "Multiple faces found"

    encodings = face_recognition.face_encodings(image_rgb, known_face_locations=locations)
    if not encodings:
        return None, "Face encoding failed"

    normalized = _normalize_encoding(encodings[0])
    if normalized is None:
        return None, f"Invalid face encoding dimension; expected {EMBEDDING_SIZE}"

    message = "Face detected after low-light enhancement — accepted." if enhanced_used else None
    return normalized, message


def save_student_encodings(
    student_id: str,
    name: str,
    encodings: list[np.ndarray],
    encodings_path: str | Path = ENCODINGS_PATH,
) -> None:
    if len(encodings) < MIN_ENROLLMENT_IMAGES or len(encodings) > MAX_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Enrollment requires {MIN_ENROLLMENT_IMAGES}-{MAX_ENROLLMENT_IMAGES} valid face images"
        )

    known_faces = load_known_faces(encodings_path)
    remaining_indexes = [
        index
        for index, existing_id in enumerate(known_faces["student_ids"])
        if existing_id != student_id
    ]
    known_faces = {
        "student_ids": [known_faces["student_ids"][index] for index in remaining_indexes],
        "names": [known_faces["names"][index] for index in remaining_indexes],
        "encodings": [known_faces["encodings"][index] for index in remaining_indexes],
    }

    for encoding in encodings:
        normalized = _normalize_encoding(encoding)
        if normalized is None:
            raise EnrollmentValidationError(
                f"Invalid face encoding dimension; expected {EMBEDDING_SIZE}"
            )
        known_faces["student_ids"].append(student_id)
        known_faces["names"].append(name)
        known_faces["encodings"].append(normalized)
    save_known_faces(known_faces, encodings_path)


def enroll_from_images(
    student_id: str,
    name: str,
    images_dir: str | Path,
    encodings_path: str | Path = ENCODINGS_PATH,
) -> int:
    images_path = Path(images_dir)
    image_files = sorted(
        path
        for path in images_path.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not image_files:
        raise RuntimeError(f"No images found in: {images_path}")

    collected_encodings: list[np.ndarray] = []
    results: list[dict] = []
    for image_path in image_files:
        encoding, msg_or_error = extract_enrollment_encoding(image_path.read_bytes())
        accepted = encoding is not None
        results.append(
            {
                "filename": image_path.name,
                "accepted": accepted,
                "message": msg_or_error if msg_or_error else ("Accepted" if accepted else "Face encoding failed"),
            }
        )
        if not accepted or encoding is None:
            continue
        collected_encodings.append(encoding)

    if len(collected_encodings) < MIN_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Enrollment requires at least {MIN_ENROLLMENT_IMAGES} valid face images",
            results=results,
        )
    if len(collected_encodings) > MAX_ENROLLMENT_IMAGES:
        raise EnrollmentValidationError(
            f"Enrollment allows at most {MAX_ENROLLMENT_IMAGES} valid face images",
            results=results,
        )

    save_student_encodings(student_id, name, collected_encodings, encodings_path)
    return len(collected_encodings)


def recognize_in_frame(
    frame_bgr: np.ndarray,
    known_faces: KnownFaces,
    tolerance: float = 0.5,
) -> list[dict]:
    height, width = frame_bgr.shape[:2]
    max_dim = max(height, width)
    scale = 1.0
    if max_dim > 640:
        scale = 640.0 / max_dim
        new_width = max(1, int(width * scale))
        new_height = max(1, int(height * scale))
        proc_bgr = cv2.resize(frame_bgr, (new_width, new_height), interpolation=cv2.INTER_AREA)
    else:
        proc_bgr = frame_bgr

    frame_rgb = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2RGB)
    frame_rgb = np.ascontiguousarray(frame_rgb)
    face_locations = face_recognition.face_locations(frame_rgb, model="hog")
    if not face_locations and scale == 1.0:
        face_locations = face_recognition.face_locations(
            frame_rgb,
            number_of_times_to_upsample=1,
            model="hog",
        )
    face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)

    if scale != 1.0 and face_locations:
        inv_scale = 1.0 / scale
        face_locations = [
            (
                int(top * inv_scale),
                int(right * inv_scale),
                int(bottom * inv_scale),
                int(left * inv_scale),
            )
            for (top, right, bottom, left) in face_locations
        ]

    sanitized = _sanitize_known_faces(known_faces)
    known_encodings = sanitized["encodings"]
    known_student_ids = sanitized["student_ids"]
    known_names = sanitized["names"]
    known_matrix = np.vstack(known_encodings) if known_encodings else np.empty((0, EMBEDDING_SIZE))

    results: list[dict] = []
    for location, face_encoding in zip(face_locations, face_encodings):
        normalized_face = _normalize_encoding(face_encoding)
        if normalized_face is None or known_matrix.shape[0] == 0:
            results.append(
                {
                    "location": location,
                    "student_id": "Unknown",
                    "name": "Unknown",
                    "distance": 1.0,
                    "matched": False,
                    "best_student_id": None,
                    "best_name": None,
                    "threshold": tolerance,
                    "reason": "no_known_encodings" if known_matrix.shape[0] == 0 else "invalid_face_encoding",
                }
            )
            continue

        distances = face_recognition.face_distance(known_matrix, normalized_face)
        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        is_match = best_distance <= tolerance
        best_student_id = known_student_ids[best_index]
        best_name = known_names[best_index]

        if is_match:
            student_id = best_student_id
            name = best_name
        else:
            student_id = "Unknown"
            name = "Unknown"

        results.append(
            {
                "location": location,
                "student_id": student_id,
                "name": name,
                "distance": best_distance,
                "matched": is_match,
                "best_student_id": best_student_id,
                "best_name": best_name,
                "threshold": tolerance,
                "reason": "matched" if is_match else "distance_above_threshold",
            }
        )
    return results
