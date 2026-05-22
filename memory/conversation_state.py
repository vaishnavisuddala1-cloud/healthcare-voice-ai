from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ConversationState:
    def __init__(self, session_id: str, language: str = "en"):
        """Initialize conversation state."""
        self.session_id = session_id
        self.language = language
        self.context = {}
        self.current_intent = None
        self.user_profile = {}

    def update_context(self, key: str, value):
        """Update conversation context."""
        self.context[key] = value

    def get_context(self, key: str) -> Optional:
        """Get context value."""
        return self.context.get(key)

    def set_user_profile(self, profile: Dict):
        """Set user profile."""
        self.user_profile = profile

    def get_user_profile(self) -> Dict:
        """Get user profile."""
        return self.user_profile

    def set_intent(self, intent: str):
        """Set current intent."""
        self.current_intent = intent

    def get_intent(self) -> Optional[str]:
        """Get current intent."""
        return self.current_intent

    def reset(self):
        """Reset conversation state."""
        self.context = {}
        self.current_intent = None
        self.user_profile = {}

    def to_dict(self) -> Dict:
        """Convert state to dictionary."""
        return {
            "session_id": self.session_id,
            "language": self.language,
            "context": self.context,
            "current_intent": self.current_intent,
            "user_profile": self.user_profile,
        }
