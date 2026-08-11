import cv2
import numpy as np

from app.face_utils import enroll_from_images, extract_enrollment_encoding, load_known_faces, recognize_in_frame


def _jpeg_bytes() -> bytes:
    image = np.full((240, 240, 3), 127, dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok is True
    return buffer.tobytes()


def test_recognize_in_frame_ignores_invalid_known_encodings(monkeypatch) -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    known_faces = {
        "student_ids": ["bad-student"],
        "names": ["Bad"],
        "encodings": [np.zeros(512)],
    }

    monkeypatch.setattr("app.face_utils.face_recognition.face_locations", lambda *_args, **_kwargs: [(0, 1, 1, 0)])
    monkeypatch.setattr(
        "app.face_utils.face_recognition.face_encodings",
        lambda *_args, **_kwargs: [np.zeros(128)],
    )

    results = recognize_in_frame(frame, known_faces, tolerance=0.5)
    assert len(results) == 1
    assert results[0]["matched"] is False
    assert results[0]["student_id"] == "Unknown"


def test_recognize_in_frame_matches_with_mixed_valid_and_invalid(monkeypatch) -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    probe = np.ones(128, dtype=np.float64)
    known_faces = {
        "student_ids": ["bad", "good"],
        "names": ["Bad", "Good Student"],
        "encodings": [np.zeros(512), np.ones(128)],
    }

    monkeypatch.setattr("app.face_utils.face_recognition.face_locations", lambda *_args, **_kwargs: [(0, 1, 1, 0)])
    monkeypatch.setattr(
        "app.face_utils.face_recognition.face_encodings",
        lambda *_args, **_kwargs: [probe],
    )

    results = recognize_in_frame(frame, known_faces, tolerance=0.5)
    assert len(results) == 1
    assert results[0]["matched"] is True
    assert results[0]["student_id"] == "good"
    assert results[0]["name"] == "Good Student"


def test_extract_enrollment_encoding_rejects_no_face(monkeypatch) -> None:
    monkeypatch.setattr("app.face_utils._quality_issue", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.face_utils.face_recognition.face_locations", lambda *_args, **_kwargs: [])

    encoding, error = extract_enrollment_encoding(_jpeg_bytes())

    assert encoding is None
    assert error == "No face found"


def test_extract_enrollment_encoding_rejects_multiple_faces(monkeypatch) -> None:
    monkeypatch.setattr("app.face_utils._quality_issue", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.face_utils.face_recognition.face_locations",
        lambda *_args, **_kwargs: [(0, 10, 10, 0), (20, 30, 30, 20)],
    )

    encoding, error = extract_enrollment_encoding(_jpeg_bytes())

    assert encoding is None
    assert error == "Multiple faces found"


def test_enroll_from_images_stores_each_valid_sample(tmp_path, monkeypatch) -> None:
    images_dir = tmp_path / "student-images"
    images_dir.mkdir()
    for index in range(5):
        (images_dir / f"face-{index}.jpg").write_bytes(b"fake")

    encodings_path = tmp_path / "encodings.pkl"
    existing = {
        "student_ids": ["same-student", "other-student"],
        "names": ["Old Name", "Other"],
        "encodings": [np.full(128, 9.0), np.full(128, 3.0)],
    }
    monkeypatch.setattr("app.face_utils.load_known_faces", lambda *_args, **_kwargs: existing)

    sample_encodings = iter([np.full(128, value) for value in (0.1, 0.2, 0.3, 0.4, 0.5)])
    monkeypatch.setattr(
        "app.face_utils.extract_enrollment_encoding",
        lambda *_args, **_kwargs: (next(sample_encodings), None),
    )

    valid_images = enroll_from_images(
        student_id="same-student",
        name="New Name",
        images_dir=images_dir,
        encodings_path=encodings_path,
    )

    saved = load_known_faces(encodings_path)
    assert valid_images == 5
    assert saved["student_ids"].count("same-student") == 5
    assert saved["student_ids"].count("other-student") == 1
    assert saved["names"].count("New Name") == 5
