from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field


class Settings(BaseSettings):
    # API Settings
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Healthcare Voice AI Agent"
    api_version: str = "1.0.0"

    # Database
    database_url: str = "postgresql://user:password@localhost:5432/voice_ai_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Whisper STT
    whisper_model: str = "base"

    # OpenAI LLM (optional — rule-based agent works without it)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Gemini LLM (optional)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # LLM provider selection: openai or gemini
    llm_provider: str = "openai"
    use_llm_agent: bool = False

    # Local LLM (gpt4all) support
    local_llm_model_path: str = ""  # path or model name for local gpt4all model
    local_llm_backend: str = "gpt4all"

    # Multilingual Support (comma-separated string, parsed to list)
    supported_languages: str = "en,hi,ta"
    default_language: str = "en"

    # CORS
    cors_origins: List[str] = Field(default=["*"])

    # JWT
    secret_key: str = "your-secret-key-change-this"
    algorithm: str = "HS256"

    # Latency Thresholds (milliseconds)
    stt_max_latency: int = 120
    agent_max_latency: int = 200
    tts_max_latency: int = 100
    total_max_latency: int = 450

    @property
    def supported_languages_list(self) -> List[str]:
        """Parse comma-separated languages to list."""
        return [lang.strip() for lang in self.supported_languages.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
