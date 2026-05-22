import logging
from config.settings import settings

logger = logging.getLogger(__name__)


class LocalGPT4All:
    """Wrapper for local gpt4all model.

    This wrapper attempts to import `gpt4all` at runtime so the project
    doesn't hard-fail if the package isn't installed yet. Use
    `settings.local_llm_model_path` to point to a downloaded model file
    (or a model name recognized by the library).
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or settings.local_llm_model_path
        self.model = None

        try:
            from gpt4all import GPT4All

            # Initialize model lazily to avoid long startup times in tests
            self.GPT4All = GPT4All
        except Exception as e:
            logger.warning("gpt4all import failed: %s", e)
            self.GPT4All = None

    def _ensure_model(self):
        if self.model is None:
            if not self.GPT4All:
                raise RuntimeError("gpt4all package not available")
            try:
                # model_name accepts either a model alias or a path depending on installation
                self.model = self.GPT4All(model_name=self.model_path or "gpt4all")
            except TypeError:
                # Fallback API variant
                self.model = self.GPT4All(self.model_path or "gpt4all")

    def generate(self, prompt: str, max_tokens: int = 150, temperature: float = 0.7) -> str:
        try:
            self._ensure_model()
            # GPT4All's generate may return a string or a dict depending on version
            out = self.model.generate(prompt, max_tokens=max_tokens, temperature=temperature)
            if isinstance(out, str):
                return out
            if isinstance(out, dict):
                # common key
                return out.get("response") or out.get("text") or str(out)
            return str(out)
        except Exception as e:
            logger.error("Local LLM generation error: %s", e, exc_info=True)
            return f"[local-llm-error] {e}"
