import pickle
import tempfile
from pathlib import Path

import face_recognition
import cv2
import numpy as np

from app.config import ENCODINGS_PATH

KnownFaces = dict[str, list]
EMBEDDING_SIZE = 128


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
    for image_path in image_files:
        image = face_recognition.load_image_file(str(image_path))
        locations = face_recognition.face_locations(image, model="hog")
        if len(locations) != 1:
            continue
        encodings = face_recognition.face_encodings(image, known_face_locations=locations)
        if encodings:
            normalized = _normalize_encoding(encodings[0])
            if normalized is not None:
                collected_encodings.append(normalized)

    if not collected_encodings:
        raise RuntimeError(
            "No valid face encodings extracted. Ensure each image has one clear face."
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

    for encoding in collected_encodings:
        known_faces["student_ids"].append(student_id)
        known_faces["names"].append(name)
        known_faces["encodings"].append(encoding)
    save_known_faces(known_faces, encodings_path)
    return len(collected_encodings)


def recognize_in_frame(
    frame_bgr: np.ndarray,
    known_faces: KnownFaces,
    tolerance: float = 0.5,
) -> list[dict]:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    frame_rgb = np.ascontiguousarray(frame_rgb)
    face_locations = face_recognition.face_locations(frame_rgb, model="hog")
    if not face_locations:
        # Retry with upsampling for small or slightly blurred webcam faces.
        face_locations = face_recognition.face_locations(
            frame_rgb,
            number_of_times_to_upsample=1,
            model="hog",
        )
    face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)

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
                }
            )
            continue

        distances = face_recognition.face_distance(known_matrix, normalized_face)
        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        is_match = best_distance <= tolerance

        if is_match:
            student_id = known_student_ids[best_index]
            name = known_names[best_index]
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
            }
        )
    return results
