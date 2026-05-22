import logging
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    BOOK_APPOINTMENT = "book_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"
    CHECK_STATUS = "check_status"
    GENERAL_INQUIRY = "general_inquiry"
    SYMPTOM_CHECKER = "symptom_checker"
    MEDICATION_INFO = "medication_info"
    NONE = "none"


class IntentClassifier:
    """Classify user intents based on input."""

    # Intent keywords in multiple languages
    INTENT_KEYWORDS = {
        IntentType.BOOK_APPOINTMENT: {
            "en": ["book", "appointment", "schedule", "doctor", "visit", "consult", "reserve", "make"],
            "es": ["reservar", "cita", "programar", "doctor", "consulta", "agendar"],
            "fr": ["réserver", "rendez-vous", "rendez vous", "docteur", "consultation", "agenda"],
            "de": ["buchen", "termin", "zeitplan", "arzt", "beratung"],
            "zh": ["预约", "预定", "医生", "咨询"],
        },
        IntentType.CANCEL_APPOINTMENT: {
            "en": ["cancel", "delete", "remove"],
            "es": ["cancelar", "eliminar"],
            "fr": ["annuler", "supprimer"],
            "de": ["stornieren", "löschen"],
            "zh": ["取消", "删除"],
        },
        IntentType.RESCHEDULE_APPOINTMENT: {
            "en": ["reschedule", "change", "move", "postpone", "shift", "rescheduled"],
            "es": ["cambiar", "posponer", "reprogramar"],
            "fr": ["modifier", "reporter", "reprogrammer"],
            "de": ["verschieben", "ändern", "neu planen"],
            "zh": ["改期", "重新安排", "延期"],
        },
        IntentType.CHECK_STATUS: {
            "en": [
                "check status",
                "appointment status",
                "status of my",
                "check the appointment",
                "check my appointment",
                "what time is my",
                "when is my appointment",
                "confirm appointment",
                "my appointment details",
            ],
            "es": ["estado", "confirmar", "cuándo", "detalles"],
            "fr": ["statut", "confirmer", "quand", "détails"],
            "de": ["status", "bestätigen", "wann", "details"],
            "zh": ["状态", "确认", "何时"],
        },
        IntentType.SYMPTOM_CHECKER: {
            "en": ["symptoms", "pain", "sick", "fever", "cough", "problem", "hurt", "ill", "disease"],
            "es": ["síntomas", "dolor", "enfermo", "fiebre", "tos", "problema"],
            "fr": ["symptômes", "douleur", "malade", "fièvre", "toux"],
            "de": ["symptome", "schmerz", "krank", "fieber", "husten"],
        },
    }

    @classmethod
    def classify(cls, user_input: str, language: str = "en") -> IntentType:
        """Classify user input intent."""
        user_input_lower = user_input.lower()

        # Get language-specific keywords
        lang_keywords = {}
        for intent, langs in cls.INTENT_KEYWORDS.items():
            if language in langs:
                lang_keywords[intent] = langs[language]
            else:
                lang_keywords[intent] = langs.get("en", [])

        # Match keywords — destructive intents before generic "appointment"
        priority = [
            IntentType.RESCHEDULE_APPOINTMENT,
            IntentType.CANCEL_APPOINTMENT,
            IntentType.CHECK_STATUS,
            IntentType.SYMPTOM_CHECKER,
            IntentType.BOOK_APPOINTMENT,
        ]
        for intent in priority:
            keywords = lang_keywords.get(intent, [])
            if any(keyword in user_input_lower for keyword in keywords):
                return intent

        return IntentType.GENERAL_INQUIRY

    @classmethod
    def get_intent_details(cls, intent: IntentType) -> Dict:
        """Get details for an intent."""
        details = {
            IntentType.BOOK_APPOINTMENT: {
                "name": "Book Appointment",
                "requires_user_input": True,
                "fields": ["date", "time", "reason", "doctor_preference"],
            },
            IntentType.CANCEL_APPOINTMENT: {
                "name": "Cancel Appointment",
                "requires_user_input": True,
                "fields": ["appointment_id", "reason"],
            },
            IntentType.RESCHEDULE_APPOINTMENT: {
                "name": "Reschedule Appointment",
                "requires_user_input": True,
                "fields": ["appointment_id", "date", "time"],
            },
            IntentType.CHECK_STATUS: {
                "name": "Check Appointment Status",
                "requires_user_input": True,
                "fields": ["appointment_id", "phone_number"],
            },
            IntentType.SYMPTOM_CHECKER: {
                "name": "Symptom Checker",
                "requires_user_input": True,
                "fields": ["symptoms", "duration", "severity"],
            },
            IntentType.GENERAL_INQUIRY: {
                "name": "General Inquiry",
                "requires_user_input": False,
                "fields": [],
            },
        }
        return details.get(intent, {})
