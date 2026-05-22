"""
Quick start guide for the Healthcare Voice AI Agent
"""

import asyncio
from services.stt_service import WhisperSTTService
from services.agent_service import HealthcareAgent
from agent.intent_classifier import IntentClassifier, IntentType
from agent.entity_extractor import EntityExtractor
from memory.memory_manager import MemoryManager


async def main():
    """Quick start example."""

    # 1. Initialize services
    print("Initializing services...")
    stt = WhisperSTTService()
    agent = HealthcareAgent()
    memory = MemoryManager()

    # 2. Simulate user input
    user_input = "I want to book an appointment with a cardiologist tomorrow at 2 PM"
    language = "en"
    session_id = "session-001"

    print(f"\nUser: {user_input}")

    # 3. Classify intent
    intent = IntentClassifier.classify(user_input, language)
    print(f"\nDetected Intent: {intent.value}")

    # 4. Extract entities
    entities = EntityExtractor.extract_entities(user_input)
    print(f"Extracted Entities: {entities}")

    # 5. Process with agent
    response = await agent.process_input(user_input, language, session_id)
    print(f"\nAgent Response:")
    print(f"  Message: {response.get('message')}")
    print(f"  Action: {response.get('action')}")

    # 6. Store in memory
    await memory.store_patient_context(
        "555-123-4567",
        {
            "language": language,
            "last_intent": intent.value,
            "entities": entities,
        }
    )

    print(f"\nConversation stored in memory for session: {session_id}")

    # 7. Retrieve context
    context = await memory.retrieve_patient_context("555-123-4567")
    print(f"Retrieved Context: {context}")


if __name__ == "__main__":
    asyncio.run(main())
