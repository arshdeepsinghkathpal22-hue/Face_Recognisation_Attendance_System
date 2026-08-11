import numpy as np

from app.face_utils import enroll_from_images, load_known_faces, recognize_in_frame


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


def test_enroll_from_images_stores_each_valid_sample(tmp_path, monkeypatch) -> None:
    images_dir = tmp_path / "student-images"
    images_dir.mkdir()
    for index in range(3):
        (images_dir / f"face-{index}.jpg").write_bytes(b"fake")

    encodings_path = tmp_path / "encodings.pkl"
    existing = {
        "student_ids": ["same-student", "other-student"],
        "names": ["Old Name", "Other"],
        "encodings": [np.full(128, 9.0), np.full(128, 3.0)],
    }
    monkeypatch.setattr("app.face_utils.load_known_faces", lambda *_args, **_kwargs: existing)
    monkeypatch.setattr("app.face_utils.face_recognition.load_image_file", lambda *_args, **_kwargs: np.zeros((10, 10, 3)))
    monkeypatch.setattr("app.face_utils.face_recognition.face_locations", lambda *_args, **_kwargs: [(0, 1, 1, 0)])

    sample_encodings = iter([np.full(128, 0.1), np.full(128, 0.2), np.full(128, 0.3)])
    monkeypatch.setattr(
        "app.face_utils.face_recognition.face_encodings",
        lambda *_args, **_kwargs: [next(sample_encodings)],
    )

    valid_images = enroll_from_images(
        student_id="same-student",
        name="New Name",
        images_dir=images_dir,
        encodings_path=encodings_path,
    )

    saved = load_known_faces(encodings_path)
    assert valid_images == 3
    assert saved["student_ids"].count("same-student") == 3
    assert saved["student_ids"].count("other-student") == 1
    assert saved["names"].count("New Name") == 3
