import time
import cv2
import numpy as np
import pytest
from app.face_utils import (
    enhance_low_light_image,
    extract_enrollment_encoding,
    recognize_in_frame,
    _quality_issue,
)
from app.api.teacher import _get_session_known_faces, _invalidate_known_faces_cache


def _create_synthetic_face_image(dark: bool = False) -> np.ndarray:
    """Generate a synthetic face-like image for testing."""
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    base_val = 25 if dark else 180
    cv2.rectangle(image, (50, 50), (590, 430), (base_val, base_val, base_val), -1)
    return image


def test_low_light_image_enhancement():
    dark_image = _create_synthetic_face_image(dark=True)
    dark_gray = cv2.cvtColor(dark_image, cv2.COLOR_RGB2GRAY)
    initial_brightness = float(np.mean(dark_gray))

    enhanced_image = enhance_low_light_image(dark_image)
    enhanced_gray = cv2.cvtColor(enhanced_image, cv2.COLOR_RGB2GRAY)
    enhanced_brightness = float(np.mean(enhanced_gray))

    assert enhanced_brightness > initial_brightness
    assert enhanced_image.shape == dark_image.shape


def _textured_image(brightness_val: int) -> np.ndarray:
    img = np.full((200, 200, 3), brightness_val, dtype=np.uint8)
    noise = np.random.randint(-5, 6, (200, 200, 3), dtype=np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def test_quality_issue_low_light_thresholds():
    dark = _textured_image(10)
    medium_dark = _textured_image(25)
    normal = _textured_image(120)

    assert _quality_issue(dark) == "Image is too dark"
    assert _quality_issue(medium_dark) is None  # Allowed for low-light enhancement attempt
    assert _quality_issue(normal) is None


def test_recognize_in_frame_speed_downscaling():
    large_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    known_faces = {
        "student_ids": ["22BCS001"],
        "names": ["Test Student"],
        "encodings": [np.ones(128, dtype=np.float64)],
    }

    start = time.perf_counter()
    results = recognize_in_frame(large_frame, known_faces, tolerance=0.5)
    elapsed = time.perf_counter() - start

    # Frame processing with downscaling should be well under 0.5s on any standard environment
    assert elapsed < 1.0
    assert isinstance(results, list)


def test_session_encodings_cache(tmp_path, monkeypatch):
    _invalidate_known_faces_cache()

    db_path = str(tmp_path / "test.db")
    known_faces_mock = {
        "student_ids": ["22BCS001"],
        "names": ["Alice"],
        "encodings": [np.zeros(128)],
    }
    monkeypatch.setattr("app.api.teacher.load_known_faces", lambda *_args, **_kwargs: known_faces_mock)
    monkeypatch.setattr("app.api.teacher.list_students", lambda db_path: [{"student_id": "22BCS001", "name": "Alice", "batch": "F5"}])
    monkeypatch.setattr("app.api.teacher.ENCODINGS_PATH", str(tmp_path / "encodings.pkl"))
    (tmp_path / "encodings.pkl").write_bytes(b"dummy")

    f1, d1 = _get_session_known_faces(session_id=1, session_batch="F5", db_path=db_path)
    f2, d2 = _get_session_known_faces(session_id=1, session_batch="F5", db_path=db_path)

    # Identical object from cache
    assert f1 is f2
