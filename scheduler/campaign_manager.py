import asyncio
import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

from scheduler.appointment_engine import AppointmentEngine
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

OnSendCallback = Callable[[str, str], Awaitable[None]]


class CampaignManager:
    """Outbound campaign scheduler for reminders and follow-ups."""

    def __init__(self):
        self.engine = AppointmentEngine()
        self.memory_manager = MemoryManager()
        self.scheduled_tasks = []

    def schedule_reminder(
        self,
        phone_number: str,
        appointment_id: int,
        send_at: datetime,
        message: str,
        on_send: Optional[OnSendCallback] = None,
        language: str = "en",
    ):
        delay = max(0, (send_at - datetime.utcnow()).total_seconds())
        task = asyncio.create_task(
            self._send_reminder(delay, phone_number, appointment_id, message, on_send, language)
        )
        self.scheduled_tasks.append(task)
        logger.info(f"Scheduled reminder for appointment {appointment_id} at {send_at.isoformat()}")

    async def _send_reminder(
        self,
        delay: float,
        phone_number: str,
        appointment_id: int,
        message: str,
        on_send: Optional[OnSendCallback],
        language: str,
    ):
        await asyncio.sleep(delay)
        appointment = self.engine.get_appointment(appointment_id)
        if not appointment:
            logger.warning(f"Reminder: appointment {appointment_id} not found")
            return

        await self.memory_manager.store_conversation(
            f"campaign:{appointment_id}",
            [{"role": "agent", "content": message, "timestamp": datetime.utcnow().isoformat()}],
            ttl=604800,
        )

        if on_send:
            await on_send(message, language)

        logger.info(
            f"Outbound reminder sent for appointment {appointment_id} to {phone_number}"
        )

    async def run_daily_reminders(self, within_hours: int = 24):
        """Scan upcoming appointments and enqueue reminder campaigns."""
        upcoming = self.engine.get_upcoming_for_campaigns(within_hours)
        for appt in upcoming:
            msg = (
                f"Hello, this is a reminder about your appointment with "
                f"{appt.doctor_name} on {appt.appointment_date.strftime('%Y-%m-%d at %H:%M')}."
            )
            self.schedule_reminder(
                appt.phone_number,
                appt.id,
                datetime.utcnow(),
                msg,
                language=appt.language or "en",
            )
        return len(upcoming)
