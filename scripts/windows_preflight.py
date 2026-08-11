import argparse
import importlib.util
import platform
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_IMPORTS = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("itsdangerous", "itsdangerous"),
    ("multipart", "python-multipart"),
    ("numpy", "numpy"),
    ("cv2", "opencv-python"),
    ("face_recognition", "face-recognition"),
    ("pytest", "pytest"),
    ("httpx", "httpx"),
]


def check_python() -> int:
    version = sys.version_info
    print(f"Python: {platform.python_version()} ({sys.executable})")
    if version < (3, 10) or version >= (3, 12):
        print(
            "ERROR: Use Python 3.10 or 3.11 on Windows. "
            "The face-recognition/dlib stack is unreliable on Python 3.12+."
        )
        return 1
    return 0


def check_project_dirs() -> None:
    for relative in ("data", "data/students", "data/models", "reports"):
        path = PROJECT_ROOT / relative
        path.mkdir(parents=True, exist_ok=True)
        print(f"OK: {path}")


def check_imports() -> int:
    missing = []
    for module_name, package_name in REQUIRED_IMPORTS:
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
        else:
            print(f"OK import: {module_name}")

    if missing:
        print("ERROR: Missing Python packages: " + ", ".join(missing))
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows setup checks for the attendance app.")
    parser.add_argument(
        "--mode",
        choices=("python", "dirs", "imports", "all"),
        default="all",
    )
    args = parser.parse_args()

    status = 0
    if args.mode in {"python", "all"}:
        status |= check_python()
    if args.mode in {"dirs", "all"}:
        check_project_dirs()
    if args.mode in {"imports", "all"}:
        status |= check_imports()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
