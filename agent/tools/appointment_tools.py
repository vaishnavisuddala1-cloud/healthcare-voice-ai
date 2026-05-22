"""Tool orchestration for appointment lifecycle actions."""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from scheduler.appointment_engine import AppointmentEngine

logger = logging.getLogger(__name__)


class AppointmentTools:
    """Agent-callable tools backed by the scheduling engine."""

    def __init__(self):
        self.engine = AppointmentEngine()

    def check_availability(self, doctor_name: str, appointment_datetime: datetime) -> Dict:
        available = self.engine.check_availability(doctor_name, appointment_datetime)
        alternatives = []
        if not available:
            alternatives = self.engine.suggest_alternatives(doctor_name, appointment_datetime)
        return {
            "available": available,
            "doctor": doctor_name,
            "requested_slot": appointment_datetime.isoformat(),
            "alternatives": alternatives,
        }

    def book_appointment(
        self,
        phone_number: str,
        doctor_name: str,
        appointment_datetime: datetime,
        reason: str = "",
        language: str = "en",
        patient_name: str = "Patient",
    ) -> Dict:
        return self.engine.book_appointment(
            phone_number=phone_number,
            doctor_name=doctor_name,
            appointment_datetime=appointment_datetime,
            reason=reason,
            language=language,
            patient_name=patient_name,
        )

    def cancel_appointment(self, appointment_id: int) -> Dict:
        appointment = self.engine.cancel_appointment(appointment_id)
        if not appointment:
            return {"success": False, "message": f"Appointment {appointment_id} not found."}
        return {"success": True, "appointment_id": appointment_id, "status": "cancelled"}

    def reschedule_appointment(self, appointment_id: int, new_datetime: datetime) -> Dict:
        appointment = self.engine.reschedule_appointment(appointment_id, new_datetime)
        if appointment:
            return {
                "success": True,
                "appointment_id": appointment_id,
                "new_date": new_datetime.isoformat(),
            }
        alternatives = self.engine.suggest_alternatives("general physician", new_datetime)
        return {
            "success": False,
            "message": "Requested slot is unavailable.",
            "alternatives": alternatives,
        }

    def get_appointment_status(self, appointment_id: int) -> Dict:
        appointment = self.engine.get_appointment(appointment_id)
        if not appointment:
            return {"found": False}
        return {
            "found": True,
            "appointment_id": appointment.id,
            "doctor_name": appointment.doctor_name,
            "status": appointment.status.value,
            "appointment_date": appointment.appointment_date.isoformat(),
        }
