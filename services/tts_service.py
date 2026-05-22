import logging
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
import pyttsx3

logger = logging.getLogger(__name__)


class TextToSpeechService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        try:
            self.engine = pyttsx3.init()
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3: {e}")
            self.engine = None

    def _synthesize_to_file(self, text: str, output_path: str):
        engine = pyttsx3.init() if self.engine is None else self.engine
        engine.save_to_file(text, output_path)
        engine.runAndWait()

    def synthesize(self, text: str) -> bytes:
        if not text:
            return b""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            path = tmp.name
        try:
            self._synthesize_to_file(text, path)
            with open(path, "rb") as f:
                data = f.read()
            return data
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    async def synthesize_async(self, text: str) -> bytes:
        loop = __import__("asyncio").get_event_loop()
        return await loop.run_in_executor(self.executor, self.synthesize, text)
