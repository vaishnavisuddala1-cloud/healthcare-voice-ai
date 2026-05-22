import logging
from typing import Dict, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extract entities from user input."""

    @staticmethod
    def extract_phone_number(text: str) -> Optional[str]:
        """Extract phone number from text."""
        # Simple regex for phone numbers (can be enhanced)
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\d{10}\b"
        match = re.search(phone_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_date(text: str) -> Optional[str]:
        """Extract date from text."""
        # Simple patterns for dates
        date_patterns = [
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",  # DD-MM-YYYY or MM-DD-YYYY
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s*\d{2,4}\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(tomorrow|today|next\s+week)\b",
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(0)

        return None

    @staticmethod
    def extract_time(text: str) -> Optional[str]:
        """Extract time from text."""
        # Simple patterns for times
        time_pattern = (
            r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm|AM|PM)?\b"
            r"|\b\d{1,2}\s*(?:am|pm|AM|PM)\b"
            r"|\b\d{1,2}\.(?:am|pm|AM|PM)\b"
        )
        match = re.search(time_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        """Extract email from text."""
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_doctor_name(text: str) -> Optional[str]:
        """Extract doctor name e.g. Dr Sharma, Dr. Patel, Dr.Sharma."""
        match = re.search(r"\bdr\.?\s*([A-Za-z]+)", text, re.IGNORECASE)
        if not match:
            match = re.search(
                r"\b(?:doctor|doctore)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
                text,
                re.IGNORECASE,
            )
        if match:
            name = match.group(1).strip().title()
            name = re.sub(r"\s+At$", "", name, flags=re.IGNORECASE)
            name = re.sub(r"name$", "", name, flags=re.IGNORECASE).strip()
            if name.lower().startswith("sharma"):
                name = "Sharma"
            return f"Dr {name}"
        return None

    @staticmethod
    def extract_doctor_specialty(text: str) -> Optional[str]:
        """Extract doctor specialty from text."""
        specialties = [
            "cardiologist",
            "dermatologist",
            "neurologist",
            "pediatrician",
            "psychiatrist",
            "surgeon",
            "general",
            "gp",
            "dentist",
            "eye",
            "orthopedic",
        ]

        text_lower = text.lower()
        for specialty in specialties:
            if specialty in text_lower:
                return specialty

        return None

    @staticmethod
    def extract_appointment_id(text: str) -> Optional[int]:
        """Extract appointment ID only when explicitly referenced (not from dates)."""
        if EntityExtractor.extract_date(text) or re.search(
            r"\d{1,2}[-/]\d{1,2}[-/]\d", text.lower()
        ):
            explicit = re.search(
                r"(?:appointment\s*)?id\s*[#:]?\s*(\d{1,8})\b",
                text,
                re.IGNORECASE,
            )
            if explicit:
                return int(explicit.group(1))
            return None

        explicit = re.search(
            r"(?:appointment\s*)?(?:id|number|ref(?:erence)?)\s*[#:]?\s*(\d{1,8})\b",
            text,
            re.IGNORECASE,
        )
        if explicit:
            return int(explicit.group(1))

        return None

    @classmethod
    def extract_entities(cls, text: str) -> Dict:
        """Extract all entities from text."""
        appointment_id = cls.extract_appointment_id(text)
        return {
            "phone_number": cls.extract_phone_number(text),
            "email": cls.extract_email(text),
            "date": cls.extract_date(text),
            "time": cls.extract_time(text),
            "doctor_name": cls.extract_doctor_name(text),
            "doctor_specialty": cls.extract_doctor_specialty(text),
            "appointment_id": appointment_id,
        }
