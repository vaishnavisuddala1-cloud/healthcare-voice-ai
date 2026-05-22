from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models import Appointment, Patient, AppointmentStatus
from backend.schemas import Appointment as AppointmentSchema, AppointmentCreate, AppointmentUpdate
from config.database import get_db
from typing import List
from datetime import datetime

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.post("/", response_model=AppointmentSchema)
async def create_appointment(
    appointment: AppointmentCreate, db: Session = Depends(get_db)
):
    """Create a new appointment booking."""
    db_appointment = Appointment(**appointment.dict())
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment


@router.get("/", response_model=List[AppointmentSchema])
async def list_appointments(
    phone_number: str = None,
    status: str = None,
    language: str = None,
    db: Session = Depends(get_db),
):
    """List appointments with optional filters."""
    query = db.query(Appointment)

    if phone_number:
        query = query.filter(Appointment.phone_number == phone_number)
    if status:
        query = query.filter(Appointment.status == status)
    if language:
        query = query.filter(Appointment.language == language)

    return query.all()


@router.get("/{appointment_id}", response_model=AppointmentSchema)
async def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Get appointment by ID."""
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.put("/{appointment_id}", response_model=AppointmentSchema)
async def update_appointment(
    appointment_id: int,
    appointment_update: AppointmentUpdate,
    db: Session = Depends(get_db),
):
    """Update appointment status."""
    db_appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()
    if not db_appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    for key, value in appointment_update.dict(exclude_unset=True).items():
        setattr(db_appointment, key, value)

    db_appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_appointment)
    return db_appointment


@router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Cancel an appointment."""
    db_appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()
    if not db_appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db_appointment.status = AppointmentStatus.CANCELLED
    db_appointment.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Appointment cancelled successfully"}


@router.get("/phone/{phone_number}")
async def get_appointments_by_phone(
    phone_number: str, db: Session = Depends(get_db)
):
    """Get all appointments for a phone number."""
    appointments = db.query(Appointment).filter(
        Appointment.phone_number == phone_number
    ).all()
    return appointments
