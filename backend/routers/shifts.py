from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.deps import get_db, require_role
from models.shift import EmployeeShiftAssignment, Shift
from models.user import User
from schemas.shifts import ShiftCreate, ShiftListResponse, ShiftOut, ShiftUpdate

router = APIRouter(prefix="/api/shifts", tags=["Shifts"])


@router.get("", response_model=ShiftListResponse, summary="List shift blocks")
def list_shifts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin", "manager")),
):
    shifts = db.query(Shift).order_by(Shift.name.asc()).all()
    return ShiftListResponse(items=shifts)


@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED, summary="Create a reusable shift block")
def create_shift(
    payload: ShiftCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin", "manager")),
):
    shift = Shift(**payload.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.put("/{shift_id}", response_model=ShiftOut, summary="Update a shift block")
def update_shift(
    shift_id: int,
    payload: ShiftUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin", "manager")),
):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    for key, value in payload.model_dump().items():
        setattr(shift, key, value)
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an unused shift block")
def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin", "manager")),
):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    in_use = (
        db.query(User).filter(User.shift_id == shift_id).first()
        or db.query(EmployeeShiftAssignment).filter(EmployeeShiftAssignment.shift_id == shift_id).first()
    )
    if in_use:
        raise HTTPException(status_code=400, detail="Shift is assigned and cannot be deleted")
    db.delete(shift)
    db.commit()
