import argparse
import sys
from pathlib import Path

import cv2

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH, ENCODINGS_PATH
from app.db import initialize_db, mark_attendance
from app.face_utils import load_known_faces, recognize_in_frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run webcam recognition and mark attendance.")
    parser.add_argument("--subject", required=True, help="Subject/session name")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index")
    parser.add_argument("--tolerance", type=float, default=0.5, help="Face distance threshold")
    parser.add_argument(
        "--confirm-frames",
        type=int,
        default=3,
        help="Frames needed before attendance is marked",
    )
    parser.add_argument("--encodings-path", default=str(ENCODINGS_PATH))
    parser.add_argument("--db-path", default=str(DB_PATH))
    return parser.parse_args()


def draw_result(frame, result: dict) -> None:
    top, right, bottom, left = result["location"]
    if result["matched"]:
        color = (0, 200, 0)
        label = f"{result['name']} ({result['distance']:.2f})"
    else:
        color = (0, 0, 255)
        label = f"Unknown ({result['distance']:.2f})"

    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
    cv2.rectangle(frame, (left, bottom - 26), (right, bottom), color, cv2.FILLED)
    cv2.putText(
        frame,
        label,
        (left + 6, bottom - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def main() -> None:
    args = parse_args()
    initialize_db(args.db_path)
    known_faces = load_known_faces(args.encodings_path)
    if not known_faces["student_ids"]:
        raise RuntimeError(
            f"No enrolled encodings found at {args.encodings_path}. Run scripts/enroll.py first."
        )

    capture = cv2.VideoCapture(args.camera_index)
    if not capture.isOpened():
        raise RuntimeError("Could not open webcam.")

    seen_streak: dict[str, int] = {}
    marked_this_session: set[str] = set()
    print("Recognition started. Press 'q' to quit.")

    try:
        while True:
            success, frame = capture.read()
            if not success:
                continue

            results = recognize_in_frame(frame, known_faces, tolerance=args.tolerance)
            ids_in_frame: set[str] = set()

            for result in results:
                draw_result(frame, result)
                if not result["matched"]:
                    continue

                student_id = result["student_id"]
                ids_in_frame.add(student_id)
                seen_streak[student_id] = seen_streak.get(student_id, 0) + 1

                if student_id in marked_this_session:
                    continue

                if seen_streak[student_id] >= args.confirm_frames:
                    inserted = mark_attendance(
                        student_id=student_id,
                        subject=args.subject,
                        confidence=1.0 - result["distance"],
                        db_path=args.db_path,
                    )
                    marked_this_session.add(student_id)
                    if inserted:
                        print(f"[ATTENDANCE] Marked: {student_id} ({args.subject})")
                    else:
                        print(f"[SKIP] Already marked today: {student_id} ({args.subject})")

            for student_id in list(seen_streak.keys()):
                if student_id not in ids_in_frame:
                    seen_streak[student_id] = 0

            cv2.putText(
                frame,
                "Press q to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Attendance Recognition", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
