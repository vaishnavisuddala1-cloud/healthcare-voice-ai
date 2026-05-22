import logging
from typing import Optional, Dict
from datetime import datetime
import json
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class HealthcareAgent:
    def __init__(self):
        """Initialize healthcare agent."""
        self.redis_client = None

    async def _get_redis(self):
        """Get Redis client."""
        if self.redis_client is None:
            from config.redis_config import get_redis
            self.redis_client = await get_redis()
        return self.redis_client

    async def process_input(
        self, user_input: str, language: str, session_id: str
    ) -> Dict:
        """Process user input and generate appropriate response."""
        try:
            # Store conversation in Redis
            redis_client = await self._get_redis()

            await self._store_message(
                redis_client, session_id, "user", user_input, language
            )

            # Analyze intent
            intent = await self._analyze_intent(user_input, language)

            # Generate response based on intent
            response = await self._generate_response(intent, user_input, language)

            # Store response in Redis
            await self._store_message(
                redis_client, session_id, "agent", response.get("message"), language
            )

            return response

        except Exception as e:
            logger.error(f"Error processing input: {e}")
            return {"error": str(e), "message": "Sorry, I encountered an error."}

    async def _analyze_intent(self, user_input: str, language: str) -> str:
        """Analyze user intent from input."""
        user_input_lower = user_input.lower()

        # Simple intent detection
        intents = {
            "book_appointment": [
                "appointment",
                "book",
                "schedule",
                "doctor",
                "visit",
                "consult",
            ],
            "cancel_appointment": ["cancel", "remove", "delete", "postpone"],
            "check_status": ["status", "when", "confirm", "details"],
            "general_info": ["hello", "hi", "help", "info", "information"],
        }

        for intent, keywords in intents.items():
            if any(keyword in user_input_lower for keyword in keywords):
                return intent

        return "general_info"

    async def _generate_response(
        self, intent: str, user_input: str, language: str
    ) -> Dict:
        """Generate response based on intent and language."""
        responses = {
            "en": {
                "book_appointment": {
                    "message": "I'd be happy to help you book an appointment. Could you please tell me your preferred date and time?",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "I can help you cancel an appointment. Could you provide your appointment ID or phone number?",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "Let me check the status of your appointment. Please provide your phone number or appointment ID.",
                    "action": "check_status",
                },
                "general_info": {
                    "message": "Hello! I'm your healthcare assistant. I can help you book appointments, check status, or answer general health questions. How can I assist you today?",
                    "action": None,
                },
            },
            "es": {
                "book_appointment": {
                    "message": "Me encantaría ayudarte a reservar una cita. ¿Cuál es tu fecha y hora preferida?",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "Puedo ayudarte a cancelar una cita. ¿Cuál es tu número de teléfono o ID de cita?",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "Déjame verificar el estado de tu cita. Por favor, proporciona tu número de teléfono o ID de cita.",
                    "action": "check_status",
                },
                "general_info": {
                    "message": "¡Hola! Soy tu asistente de salud. Puedo ayudarte a reservar citas, verificar el estado o responder preguntas generales de salud. ¿Cómo puedo ayudarte?",
                    "action": None,
                },
            },
            "fr": {
                "book_appointment": {
                    "message": "Je serais ravi de vous aider à prendre rendez-vous. Quelle est votre date et heure préférées?",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "Je peux vous aider à annuler un rendez-vous. Quel est votre numéro de téléphone ou ID de rendez-vous?",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "Laissez-moi vérifier le statut de votre rendez-vous. Veuillez fournir votre numéro de téléphone ou ID de rendez-vous.",
                    "action": "check_status",
                },
                "general_info": {
                    "message": "Bonjour! Je suis votre assistant santé. Je peux vous aider à prendre rendez-vous, vérifier le statut ou répondre à des questions générales de santé. Comment puis-je vous aider?",
                    "action": None,
                },
            },
            "de": {
                "book_appointment": {
                    "message": "Ich würde Ihnen gerne helfen, einen Termin zu buchen. Welches Datum und Uhrzeit bevorzugen Sie?",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "Ich kann Ihnen helfen, einen Termin abzusagen. Können Sie Ihre Telefonnummer oder Termin-ID angeben?",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "Lassen Sie mich den Status Ihres Termins überprüfen. Bitte geben Sie Ihre Telefonnummer oder Termin-ID an.",
                    "action": "check_status",
                },
                "general_info": {
                    "message": "Hallo! Ich bin dein Gesundheitsassistent. Ich kann dir helfen, Termine zu buchen, den Status zu überprüfen oder allgemeine Gesundheitsfragen zu beantworten. Wie kann ich dir helfen?",
                    "action": None,
                },
            },
        }

        language_responses = responses.get(language, responses["en"])
        return language_responses.get(intent, language_responses["general_info"])

    async def _store_message(
        self, redis_client, session_id: str, role: str, content: str, language: str
    ):
        """Store message in Redis for conversation history."""
        try:
            message = {
                "role": role,
                "content": content,
                "language": language,
                "timestamp": datetime.utcnow().isoformat(),
            }
            key = f"session:{session_id}:messages"
            await redis.lpush(key, json.dumps(message))
            await redis.expire(key, 86400)  # 24 hours expiry
        except Exception as e:
            logger.error(f"Error storing message in Redis: {e}")
