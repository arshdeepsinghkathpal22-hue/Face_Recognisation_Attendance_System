from fastapi import APIRouter, HTTPException, Request, status

from app.api.schemas import LoginRequest, LoginResponse, MeResponse, StudentResponse
from app.db import get_student_by_login, get_student_with_profile
from app.security import password_needs_rehash, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


def _get_authenticated_student(request: Request) -> StudentResponse:
    student_id = request.session.get("student_id")
    if not student_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    student = get_student_with_profile(student_id=student_id, db_path=request.app.state.db_path)
    if student is None:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return StudentResponse(**student)


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    db_path = request.app.state.db_path
    student = get_student_by_login(login=payload.student_id, db_path=db_path)
    if student is None or not verify_password(payload.password, student["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid student credentials",
        )
    if password_needs_rehash(student["password"]):
        from app.db import update_student_password
        update_student_password(student["student_id"], payload.password, db_path=db_path)

    request.session["student_id"] = student["student_id"]
    request.session.pop("teacher_id", None)
    request.session.pop("admin_id", None)
    return LoginResponse(ok=True, student=StudentResponse(**student))


@router.post("/auth/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    student_id = request.session.get("student_id")
    if not student_id:
        return MeResponse(logged_in=False, student=None)

    student = get_student_with_profile(student_id=student_id, db_path=request.app.state.db_path)
    if student is None:
        request.session.clear()
        return MeResponse(logged_in=False, student=None)

    return MeResponse(logged_in=True, student=StudentResponse(**student))
