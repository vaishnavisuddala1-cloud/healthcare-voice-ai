"""Long-term patient memory with in-memory fallback."""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_local_patients: Dict[str, Dict] = {}


class PersistentMemory:
    def __init__(self, ttl: int = 604800):
        self.ttl = ttl
        self._redis_ok = True

    async def get_patient_context(self, phone_number: str) -> Dict:
        try:
            from memory.memory_manager import MemoryManager
            mgr = MemoryManager()
            ctx = await mgr.retrieve_patient_context(phone_number)
            if ctx:
                return ctx
        except Exception as e:
            logger.warning(f"Persistent memory read fallback: {e}")
            self._redis_ok = False
        return _local_patients.get(phone_number, {})

    async def update_patient_context(self, phone_number: str, updates: Dict) -> Dict:
        existing = await self.get_patient_context(phone_number)
        merged = {**existing, **updates}
        try:
            from memory.memory_manager import MemoryManager
            mgr = MemoryManager()
            await mgr.store_patient_context(phone_number, merged, ttl=self.ttl)
        except Exception as e:
            logger.warning(f"Persistent memory write fallback: {e}")
            self._redis_ok = False
        _local_patients[phone_number] = merged
        return merged

    async def record_appointment_preference(
        self,
        phone_number: str,
        doctor_name: str,
        language: str,
        hospital: str = "Apollo",
    ):
        return await self.update_patient_context(
            phone_number,
            {
                "preferred_language": language,
                "last_doctor": doctor_name,
                "preferred_hospital": hospital,
            },
        )

    async def get_preferred_language(self, phone_number: str) -> Optional[str]:
        ctx = await self.get_patient_context(phone_number)
        return ctx.get("preferred_language")
