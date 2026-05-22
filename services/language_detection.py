import logging
from langdetect import detect, DetectorFactory
from config.settings import settings

DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
}


class LanguageDetectionService:
    """Detect user language from text (English, Hindi, Tamil)."""

    @staticmethod
    def detect_language(text: str) -> tuple[str, float]:
        """
        Detect language from text.

        Returns:
            Tuple of (language_code, confidence)
        """
        try:
            if not text or len(text.strip()) < 2:
                return settings.default_language, 0.0

            detected = detect(text).lower()
            supported = settings.supported_languages_list

            if detected in supported:
                logger.info(f"Detected language: {detected}")
                return detected, 0.95

            # Script-based fallback for short utterances
            if any("\u0900" <= c <= "\u097F" for c in text):
                return "hi", 0.85
            if any("\u0B80" <= c <= "\u0BFF" for c in text):
                return "ta", 0.85

            return settings.default_language, 0.5

        except Exception as e:
            logger.warning(f"Language detection error: {e}, defaulting to English")
            return settings.default_language, 0.0

    @staticmethod
    def is_supported_language(language_code: str) -> bool:
        return language_code in settings.supported_languages_list

    @staticmethod
    def get_language_name(language_code: str) -> str:
        return LANGUAGE_NAMES.get(language_code, "English")
