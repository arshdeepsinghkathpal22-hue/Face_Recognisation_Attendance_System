from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.auth import _get_authenticated_student
from app.api.schemas import AttendanceSummaryResponse, SemestersListResponse, StudentAttendanceHistoryItemResponse, StudentResponse
from app.db import list_active_semesters, list_student_attendance_history
from app.services.attendance_service import build_attendance_summary

router = APIRouter(prefix="/api", tags=["attendance"])


@router.get("/semesters", response_model=SemestersListResponse)
def get_semesters(
    request: Request,
    _: StudentResponse = Depends(_get_authenticated_student),
) -> SemestersListResponse:
    items = list_active_semesters(db_path=request.app.state.db_path)
    return SemestersListResponse(items=items)


@router.get("/attendance/summary", response_model=AttendanceSummaryResponse)
def attendance_summary(
    request: Request,
    semester_id: str = Query(..., min_length=1),
    student: StudentResponse = Depends(_get_authenticated_student),
) -> AttendanceSummaryResponse:
    try:
        summary = build_attendance_summary(
            student_id=student.student_id,
            semester_id=semester_id,
            db_path=request.app.state.db_path,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return AttendanceSummaryResponse(**summary)


@router.get("/attendance/history", response_model=list[StudentAttendanceHistoryItemResponse])
def attendance_history(
    request: Request,
    semester_id: str = Query("fall-2024", min_length=1),
    student: StudentResponse = Depends(_get_authenticated_student),
) -> list[StudentAttendanceHistoryItemResponse]:
    history = list_student_attendance_history(
        student_id=student.student_id,
        semester_id=semester_id,
        db_path=request.app.state.db_path,
    )
    return [StudentAttendanceHistoryItemResponse(**item) for item in history]

