import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from config.database import SessionLocal
from backend.models import Appointment, Patient, AppointmentStatus

logger = logging.getLogger(__name__)


def parse_natural_date(text: str) -> Optional[datetime]:
    value = text.lower().strip()
    now = datetime.utcnow()
    if "tomorrow" in value:
        return now + timedelta(days=1)
    if "today" in value:
        return now
    if "next week" in value:
        return now + timedelta(days=7)
    if "day after tomorrow" in value:
        return now + timedelta(days=2)

    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    month_match = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s*(\d{2,4})",
        value,
    )
    if month_match:
        month = month_names[month_match.group(1)]
        day = int(month_match.group(2))
        year_raw = int(month_match.group(3))
        year = year_raw if year_raw > 99 else 2000 + year_raw
        try:
            return datetime(year, month, day)
        except ValueError:
            pass

    # Try ISO-like date formats (YYYY-MM-DD or DD-MM-YYYY / DD-MM-YY)
    patterns = [
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            parts = [int(p) for p in match.groups()]
            try:
                if parts[0] > 31:
                    return datetime(parts[0], parts[1], parts[2])
                year = parts[2] if parts[2] > 99 else 2000 + parts[2]
                return datetime(year, parts[1], parts[0])
            except ValueError:
                continue
    return None


def parse_natural_time(text: str) -> Optional[datetime.time]:
    value = text.lower().strip()
    match = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*\.?\s*(am|pm)?", value)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    suffix = match.group(3)
    if suffix:
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
    try:
        return datetime.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0).time()
    except ValueError:
        return None


def parse_natural_datetime(date_text: str, time_text: str) -> Optional[datetime]:
    date = parse_natural_date(date_text or "")
    time_obj = parse_natural_time(time_text or "")
    if date and time_obj:
        return datetime.combine(date.date(), time_obj)
    if date:
        return date
    return None


class AppointmentService:
    def __init__(self):
        self.db = SessionLocal()

    def get_patient_by_phone(self, phone_number: str) -> Optional[Patient]:
        return self.db.query(Patient).filter(Patient.phone_number == phone_number).first()

    def create_patient(self, name: str, phone_number: str, email: str = None, language: str = "en") -> Patient:
        patient = self.get_patient_by_phone(phone_number)
        if patient:
            return patient
        normalized_email = email if email else None
        patient = Patient(name=name or "Patient", phone_number=phone_number, email=normalized_email, language=language)
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def check_availability(self, doctor_name: str, appointment_datetime: datetime) -> bool:
        if appointment_datetime < datetime.utcnow():
            return False
        existing = self.db.query(Appointment).filter(
            Appointment.doctor_name == doctor_name,
            Appointment.appointment_date == appointment_datetime,
            Appointment.status != AppointmentStatus.CANCELLED,
        ).first()
        return existing is None

    def suggest_alternatives(self, doctor_name: str, appointment_datetime: datetime) -> List[str]:
        suggestions = []
        for delta in [1, 2, 3, 4, 5]:
            alternative_time = appointment_datetime + timedelta(days=delta)
            if self.check_availability(doctor_name, alternative_time):
                suggestions.append(alternative_time.strftime("%Y-%m-%d %H:%M"))
            if len(suggestions) >= 3:
                break
        return suggestions

    def book_appointment(
        self,
        phone_number: str,
        doctor_name: str,
        appointment_datetime: datetime,
        reason: str,
        language: str = "en",
        patient_name: str = "Patient",
        email: Optional[str] = None,
    ) -> Dict:
        patient = self.create_patient(patient_name, phone_number, email, language)
        status = AppointmentStatus.CONFIRMED if self.check_availability(doctor_name, appointment_datetime) else AppointmentStatus.PENDING
        appointment = Appointment(
            patient_id=patient.id,
            phone_number=phone_number,
            doctor_name=doctor_name,
            appointment_date=appointment_datetime,
            reason=reason,
            language=language,
            status=status,
            confirmation_sent=False,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return {
            "appointment_id": appointment.id,
            "status": appointment.status.value,
            "doctor_name": doctor_name,
            "appointment_date": appointment_datetime.isoformat(),
            "reason": reason,
            "language": language,
        }

    def cancel_appointment(self, appointment_id: int) -> Optional[Appointment]:
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return None
        appointment.status = AppointmentStatus.CANCELLED
        appointment.updated_at = datetime.utcnow()
        self.db.commit()
        return appointment

    def reschedule_appointment(self, appointment_id: int, new_datetime: datetime) -> Optional[Appointment]:
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return None
        if not self.check_availability(appointment.doctor_name, new_datetime):
            return None
        appointment.appointment_date = new_datetime
        appointment.status = AppointmentStatus.CONFIRMED
        appointment.updated_at = datetime.utcnow()
        self.db.commit()
        return appointment

    def get_appointment(self, appointment_id: int) -> Optional[Appointment]:
        return self.db.query(Appointment).filter(Appointment.id == appointment_id).first()

    def get_upcoming_appointments(self, within_hours: int = 24) -> List[Appointment]:
        now = datetime.utcnow()
        upcoming = now + timedelta(hours=within_hours)
        return self.db.query(Appointment).filter(
            Appointment.appointment_date >= now,
            Appointment.appointment_date <= upcoming,
            Appointment.status == AppointmentStatus.CONFIRMED,
        ).all()
