import logging
from typing import Dict, Optional, List
from memory.memory_manager import MemoryManager
from memory.conversation_state import ConversationState

logger = logging.getLogger(__name__)


class DialogueManager:
    def __init__(self):
        """Initialize dialogue manager."""
        self.memory_manager = MemoryManager()
        self.conversation_states: Dict[str, ConversationState] = {}

    def create_conversation_state(
        self, session_id: str, language: str = "en"
    ) -> ConversationState:
        """Create a new conversation state."""
        state = ConversationState(session_id, language)
        self.conversation_states[session_id] = state
        logger.info(f"Created conversation state for {session_id}")
        return state

    def get_conversation_state(self, session_id: str) -> Optional[ConversationState]:
        """Get existing conversation state."""
        return self.conversation_states.get(session_id)

    def remove_conversation_state(self, session_id: str):
        """Remove conversation state."""
        if session_id in self.conversation_states:
            del self.conversation_states[session_id]
            logger.info(f"Removed conversation state for {session_id}")

    async def process_dialogue_turn(
        self, session_id: str, user_input: str, agent_response: Dict
    ) -> Dict:
        """Process a dialogue turn and update state."""
        state = self.get_conversation_state(session_id)

        if not state:
            # Create new state if doesn't exist
            language = agent_response.get("language", "en")
            state = self.create_conversation_state(session_id, language)

        # Update intent if action is specified
        if agent_response.get("action"):
            state.set_intent(agent_response.get("action"))

        # Store user input in context
        if "messages" not in state.context:
            state.context["messages"] = []

        state.context["messages"].append({
            "role": "user",
            "content": user_input,
        })

        state.context["messages"].append({
            "role": "agent",
            "content": agent_response.get("message"),
        })

        # Keep only last 20 messages to avoid memory bloat
        if len(state.context["messages"]) > 20:
            state.context["messages"] = state.context["messages"][-20:]

        return {"state": state.to_dict(), "response": agent_response}

    async def get_dialogue_context(self, session_id: str) -> Dict:
        """Get current dialogue context."""
        state = self.get_conversation_state(session_id)

        if not state:
            return {}

        return {
            "session_id": session_id,
            "language": state.language,
            "current_intent": state.current_intent,
            "context": state.context,
            "user_profile": state.user_profile,
        }

    async def end_conversation(self, session_id: str):
        """End conversation and cleanup."""
        # Store final state in Redis for future reference
        state = self.get_conversation_state(session_id)
        if state:
            await self.memory_manager.store_conversation(
                session_id,
                state.context.get("messages", []),
                ttl=604800  # 7 days
            )
        self.remove_conversation_state(session_id)
