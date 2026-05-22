import whisper
import logging
from config.settings import settings
from io import BytesIO

logger = logging.getLogger(__name__)


class WhisperSTTService:
    def __init__(self):
        """Initialize Whisper model."""
        self.model = None
        self.model_name = settings.whisper_model
        self._load_model()

    def _load_model(self):
        """Load Whisper model."""
        try:
            self.model = whisper.load_model(self.model_name)
            logger.info(f"Whisper model '{self.model_name}' loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def transcribe(self, audio_data: bytes, language: str = None) -> str:
        """Transcribe audio data using Whisper."""
        try:
            # Convert bytes to file-like object
            audio_file = BytesIO(audio_data)

            # Transcribe audio
            result = self.model.transcribe(
                audio_file,
                language=self._map_language_code(language),
                fp16=False,
            )

            text = result.get("text", "").strip()
            logger.info(f"Transcribed text: {text}")
            return text

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    @staticmethod
    def _map_language_code(language: str) -> str:
        """Map language codes to Whisper format."""
        language_map = {
            "en": "english",
            "hi": "hindi",
            "ta": "tamil",
        }
        return language_map.get(language, "english")

    async def transcribe_file(self, file_path: str, language: str = None) -> str:
        """Transcribe audio from a file."""
        try:
            with open(file_path, "rb") as f:
                audio_data = f.read()
            return await self.transcribe(audio_data, language)
        except Exception as e:
            logger.error(f"File transcription error: {e}")
            raise
