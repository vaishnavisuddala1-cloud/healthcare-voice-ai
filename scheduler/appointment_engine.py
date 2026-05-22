"""Scheduling engine: validation, conflict detection, and alternatives."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from services.appointment_service import AppointmentService

logger = logging.getLogger(__name__)


class AppointmentEngine:
    """Central scheduling logic separated from agent reasoning."""

    def __init__(self):
        self.service = AppointmentService()

    def check_availability(self, doctor_name: str, appointment_datetime: datetime) -> bool:
        return self.service.check_availability(doctor_name, appointment_datetime)

    def suggest_alternatives(self, doctor_name: str, appointment_datetime: datetime) -> List[str]:
        return self.service.suggest_alternatives(doctor_name, appointment_datetime)

    def book_appointment(
        self,
        phone_number: str,
        doctor_name: str,
        appointment_datetime: datetime,
        reason: str = "",
        language: str = "en",
        patient_name: str = "Patient",
        email: str = "",
    ) -> Dict:
        if appointment_datetime < datetime.utcnow():
            return {
                "success": False,
                "error": "past_time",
                "message": "Cannot book appointments in the past.",
            }

        if not self.check_availability(doctor_name, appointment_datetime):
            alternatives = self.suggest_alternatives(doctor_name, appointment_datetime)
            return {
                "success": False,
                "error": "conflict",
                "message": "That slot is already booked.",
                "alternatives": alternatives,
            }

        result = self.service.book_appointment(
            phone_number=phone_number,
            doctor_name=doctor_name,
            appointment_datetime=appointment_datetime,
            reason=reason,
            language=language,
            patient_name=patient_name,
            email=email,
        )
        return {"success": True, **result}

    def cancel_appointment(self, appointment_id: int):
        return self.service.cancel_appointment(appointment_id)

    def reschedule_appointment(self, appointment_id: int, new_datetime: datetime):
        appointment = self.service.get_appointment(appointment_id)
        if not appointment:
            return None
        if new_datetime < datetime.utcnow():
            return None
        if not self.check_availability(appointment.doctor_name, new_datetime):
            return None
        return self.service.reschedule_appointment(appointment_id, new_datetime)

    def get_appointment(self, appointment_id: int):
        return self.service.get_appointment(appointment_id)

    def get_upcoming_for_campaigns(self, within_hours: int = 24):
        return self.service.get_upcoming_appointments(within_hours)
