import logging
import json
from typing import Dict, Optional
from datetime import datetime
from config.settings import settings
from services.language_detection import LanguageDetectionService
from services.latency_tracker import LatencyTracker
from services.local_llm import LocalGPT4All
from services.appointment_service import parse_natural_datetime
from agent.intent_classifier import IntentClassifier
from agent.entity_extractor import EntityExtractor
from agent.tools.appointment_tools import AppointmentTools
from memory.session_memory import SessionMemory
from memory.persistent_memory import PersistentMemory
import asyncio
import functools
import httpx

logger = logging.getLogger(__name__)

try:
    import openai
    openai.api_key = settings.openai_api_key
except Exception:
    openai = None

OPENAI_PLACEHOLDER_KEYS = {"", "your_openai_api_key_here", "sk-your-key-here"}
GEMINI_PLACEHOLDER_KEYS = {"", "your_gemini_api_key_here"}


def _use_openai() -> bool:
    key = (settings.openai_api_key or "").strip()
    return bool(key and key not in OPENAI_PLACEHOLDER_KEYS and openai is not None)


def _use_gemini() -> bool:
    key = (settings.gemini_api_key or "").strip()
    return bool(key and key not in GEMINI_PLACEHOLDER_KEYS)


class HealthcareAgentV2:
    """Enhanced healthcare agent with OpenAI and latency tracking."""

    def __init__(self):
        """Initialize agent."""
        self.redis_client = None
        self.language_service = LanguageDetectionService()
        self.local_llm = LocalGPT4All()
        self.tools = AppointmentTools()
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.session_memory = SessionMemory()
        self.persistent_memory = PersistentMemory()

    async def _get_redis(self):
        """Get Redis client."""
        if self.redis_client is None:
            from config.redis_config import get_redis
            self.redis_client = await get_redis()
        return self.redis_client

    async def process_input(
        self, user_input: str, language: str, session_id: str, respect_ui_language: bool = True
    ) -> Dict:
        """
        Process user input with LLM reasoning and latency tracking.

        Args:
            user_input: User's text input
            language: Language code (en, hi, ta)
            session_id: Unique session identifier

        Returns:
            Response dict with message, action, and metadata
        """
        tracker = LatencyTracker(session_id)

        try:
            # UI language drives responses; auto-detect only when not respecting UI selection
            response_language = language
            tracker.start_stage("language_detection")
            detected_lang, confidence = self.language_service.detect_language(user_input)
            if not respect_ui_language and confidence > 0.7:
                response_language = detected_lang
            language = response_language
            tracker.end_stage("language_detection")

            tracker.start_stage("memory_lookup")
            await self.session_memory.append_message(session_id, "user", user_input, language)
            phone_hint = self.entity_extractor.extract_phone_number(user_input)
            if phone_hint:
                session_state = await self.session_memory.get_state(session_id) or {}
                session_state["last_phone_number"] = phone_hint
                await self.session_memory.set_state(session_id, session_state)
                patient_ctx = await self.persistent_memory.get_patient_context(phone_hint)
                pref_lang = patient_ctx.get("preferred_language")
                if pref_lang and respect_ui_language is False:
                    language = pref_lang
            tracker.end_stage("memory_lookup")

            tracker.start_stage("agent_reasoning")
            response = await self._process_with_rules(user_input, language, session_id)
            if settings.use_llm_agent and (_use_openai() or _use_gemini()):
                try:
                    llm_response = await self._process_with_llm(user_input, language, session_id)
                    if llm_response.get("message") and not llm_response.get("error"):
                        if (
                            response.get("action") == "book_appointment"
                            and not self._is_action_completed(response)
                        ):
                            pass
                        elif not self._is_action_completed(response):
                            response = llm_response
                except Exception as e:
                    logger.warning(f"LLM failed, keeping rule-based response: {e}")
            tracker.end_stage("agent_reasoning")

            tracker.start_stage("response_storage")
            await self.session_memory.append_message(
                session_id, "agent", response.get("message", ""), language
            )
            data = response.get("data") or {}
            if phone_hint and response.get("action") == "book_appointment" and data.get("success"):
                await self.persistent_memory.record_appointment_preference(
                    phone_hint,
                    data.get("doctor_name", ""),
                    language,
                )
            tracker.end_stage("response_storage")

            # Log latency report
            latency_report = tracker.log_report(settings.total_max_latency)

            # Add latency info to response
            response["latency_ms"] = latency_report["total_latency_ms"]
            response["latency_breakdown"] = latency_report["stages"]

            return response

        except Exception as e:
            logger.error(f"Error processing input: {e}", exc_info=True)
            return {
                "error": str(e),
                "message": self._get_error_message(language),
            }

    async def _process_with_llm(
        self, user_input: str, language: str, session_id: str
    ) -> Dict:
        """Process input using the configured LLM provider."""
        try:
            provider = (settings.llm_provider or "").strip().lower()
            if provider == "gemini" and _use_gemini():
                return await self._process_with_gemini(user_input, language, session_id)
            if provider == "openai" and _use_openai():
                return await self._process_with_openai(user_input, language, session_id)
            if _use_openai():
                return await self._process_with_openai(user_input, language, session_id)
            if _use_gemini():
                return await self._process_with_gemini(user_input, language, session_id)
            return await self._process_with_rules(user_input, language, session_id)
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            return await self._process_with_rules(user_input, language, session_id)

    async def _process_with_openai(
        self, user_input: str, language: str, session_id: str
    ) -> Dict:
        """Process input using OpenAI LLM."""
        # Build system prompt
        system_prompt = self._get_system_prompt(language)

        history = await self.session_memory.get_messages(session_id, limit=10)

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            role = "assistant" if msg.get("role") == "agent" else msg.get("role", "user")
            messages.append({"role": role, "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_input})

        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.7,
            max_tokens=150,
        )
        agent_response = response.choices[0].message.content

        action = self._extract_action(agent_response)
        return await self._handle_agent_action(
            user_input, language, session_id, agent_response, action
        )

    async def _process_with_gemini(
        self, user_input: str, language: str, session_id: str
    ) -> Dict:
        """Process input using Gemini via HTTP API."""
        system_prompt = self._get_system_prompt(language)
        history = await self.session_memory.get_messages(session_id, limit=10)

        # Build messages in Gemini format
        messages = []
        
        # Add system prompt as first user message
        messages.append({"role": "user", "parts": [{"text": system_prompt}]})
        messages.append({"role": "model", "parts": [{"text": "Understood. I will act as a professional healthcare appointment assistant."}]})
        
        # Add conversation history
        for msg in history:
            role = "user" if msg.get("role") != "agent" else "model"
            messages.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        
        # Add current user input
        messages.append({"role": "user", "parts": [{"text": user_input}]})

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
            f"?key={settings.gemini_api_key}"
        )
        payload = {
            "contents": messages,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 150,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()

        agent_response = ""
        if isinstance(result, dict):
            candidates = result.get("candidates", [])
            if candidates:
                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                if parts:
                    agent_response = parts[0].get("text", "")

        if not agent_response:
            raise RuntimeError("Gemini response did not contain text")

        action = self._extract_action(agent_response)
        return await self._handle_agent_action(
            user_input, language, session_id, agent_response, action
        )

    async def _process_with_local_llm(
        self, user_input: str, language: str, session_id: str
    ) -> Dict:
        """Process input using a local gpt4all model."""
        try:
            # Build a single prompt combining system + history + user
            system_prompt = self._get_system_prompt(language)

            history = await self.session_memory.get_messages(session_id, limit=10)

            prompt_parts = [system_prompt]
            for msg in history:
                prompt_parts.append(f"{msg['role']}: {msg['content']}")
            prompt_parts.append(f"user: {user_input}")
            prompt = "\n".join(prompt_parts)

            # Generate using local LLM in threadpool to avoid blocking
            loop = asyncio.get_event_loop()
            gen = functools.partial(self.local_llm.generate, prompt, 150, 0.7)
            agent_response = await loop.run_in_executor(None, gen)

            action = self._extract_action(agent_response)
            return await self._handle_agent_action(
                user_input, language, session_id, agent_response, action
            )

        except Exception as e:
            logger.error(f"Local LLM processing error: {e}")
            raise

    def _is_booking_confirmation(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(
            word in lower
            for word in ("yes", "correct", "confirm", "confirmed", "that's right", "right", "proceed")
        )

    def _has_booking_entities(self, entities: Dict) -> bool:
        return bool(
            entities.get("phone_number")
            and (
                entities.get("date")
                or entities.get("time")
                or entities.get("doctor_name")
                or entities.get("doctor_specialty")
            )
        )

    def _looks_like_booking(self, user_input: str, entities: Dict) -> bool:
        if self._is_services_inquiry(user_input) or self._is_status_check(user_input):
            return False
        if self._is_cancel_request(user_input):
            return False
        lower = user_input.lower()
        if any(
            phrase in lower
            for phrase in ("book", "schedule", "make an appointment", "book my", "book appointment")
        ):
            return True
        return self._has_booking_entities(entities)

    def _is_services_inquiry(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(
            phrase in lower
            for phrase in (
                "service", "provide", "what can you", "help with",
                "capabilities", "which services", "what do you do",
            )
        )

    def _is_status_check(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(
            phrase in lower
            for phrase in (
                "check status",
                "appointment status",
                "status of",
                "check my appointment",
                "check the appointment",
                "my appointment status",
                "when is my appointment",
            )
        )

    def _is_cancel_request(self, user_input: str) -> bool:
        lower = user_input.lower()
        return "cancel" in lower and ("appointment" in lower or "booking" in lower)

    async def _clear_pending_booking(self, session_id: str):
        state = await self.session_memory.get_state(session_id) or {}
        state.pop("pending_booking", None)
        await self.session_memory.set_state(session_id, state)

    async def _process_with_rules(
        self, user_input: str, language: str, session_id: str
    ) -> Dict:
        """Rule-based intent detection and tool execution (works offline)."""
        from agent.intent_classifier import IntentClassifier, IntentType

        entities = self.entity_extractor.extract_entities(user_input)
        state = await self.session_memory.get_state(session_id) or {}

        if self._is_services_inquiry(user_input):
            await self._clear_pending_booking(session_id)
            return await self._generate_response("general_info", user_input, language)

        if self._is_status_check(user_input):
            await self._clear_pending_booking(session_id)
            return await self._handle_agent_action(
                user_input, language, session_id, "", "check_status"
            )

        if self._is_cancel_request(user_input):
            await self._clear_pending_booking(session_id)
            return await self._handle_agent_action(
                user_input, language, session_id, "", "cancel_appointment"
            )

        if state.get("pending_reschedule"):
            return await self._handle_agent_action(
                user_input, language, session_id, "", "reschedule_appointment"
            )

        if state.get("pending_booking"):
            continuing_booking = (
                self._is_booking_confirmation(user_input)
                or self._has_booking_entities(entities)
                or self._looks_like_booking(user_input, entities)
            )
            if continuing_booking:
                return await self._handle_agent_action(
                    user_input, language, session_id, "", "book_appointment"
                )
            await self._clear_pending_booking(session_id)

        if self._looks_like_booking(user_input, entities):
            return await self._handle_agent_action(
                user_input, language, session_id, "", "book_appointment"
            )

        intent = IntentClassifier.classify(user_input, language)
        action_map = {
            IntentType.BOOK_APPOINTMENT: "book_appointment",
            IntentType.CANCEL_APPOINTMENT: "cancel_appointment",
            IntentType.RESCHEDULE_APPOINTMENT: "reschedule_appointment",
            IntentType.CHECK_STATUS: "check_status",
        }
        action = action_map.get(intent)
        if action in ("check_status", "cancel_appointment") and self._looks_like_booking(
            user_input, entities
        ):
            action = "book_appointment"
        if action:
            return await self._handle_agent_action(
                user_input, language, session_id, "", action
            )
        return await self._generate_response("general_info", user_input, language)

    def _get_system_prompt(self, language: str) -> str:
        """Get system prompt for LLM in specified language."""
        prompts = {
            "en": """You are a Healthcare Voice AI Assistant. Your job is to help patients book, reschedule, and cancel doctor appointments.

REQUIRED INFORMATION FOR BOOKING (ask only if missing):
1. Doctor name
2. Appointment date
3. Appointment time
4. Phone number

RULES:
- Ask only for the fields needed to complete the current appointment task
- For booking, ask for the 4 required fields above
- For rescheduling, ask only for new date and new time (use phone from the conversation if already given)
- For cancellation or status checks, ask only for phone number if appointment ID is unknown
- When the user confirms details, complete the action
- NEVER answer unrelated health questions
- If the question is unrelated, say: "I can only help with booking, rescheduling, or cancelling appointments."
- Be polite and professional""",

            "hi": """आप एक Healthcare Voice AI Assistant हैं। आपका काम है डॉक्टर की नियुक्ति बुक करना, पुनर्निर्धारित करना, और रद्द करना।

बुकिंग के लिए आवश्यक जानकारी (केवल अगर missing हो):
1. डॉक्टर का नाम
2. नियुक्ति की तारीख
3. नियुक्ति का समय
4. फोन नंबर

नियम:
- केवल उस कार्य के लिए आवश्यक जानकारी पूछें
- बुकिंग के लिए ऊपर दिए गए 4 विवरण पूछें
- पुनर्निर्धारित करने के लिए केवल नई तारीख और नया समय पूछें (फोन नंबर पहले से हो तो दोबारा न पूछें)
- रद्द करने या स्थिति जांचने के लिए फोन नंबर या अपॉइंटमेंट ID पूछें
- जब उपयोगकर्ता विवरण की पुष्टि करे, तो कार्रवाई को पूर्ण करें
- कभी भी सामान्य स्वास्थ्य सवालों का जवाब न दें
- अगर उपयोगकर्ता असंबंधित प्रश्न पूछे, तो कहें: "मैं केवल अपॉइंटमेंट बुकिंग, पुनर्निर्धारण या रद्द करने में मदद कर सकता हूं।"
- विनम्र और व्यावसायिक रहें""",

            "ta": """நீங்கள் Healthcare Voice AI Assistant. உங்கள் ONLY வேலை - டாக்டர் நியமனம் வாங்குவது.

தேவையான தகவல் (missing ஆக இருந்தால் மட்டுமே கேக்கவும்):
1. டாக்டர் பெயர்
2. நியமன தேதி
3. நியமன நேரம்
4. ফோன் எண்

விதிகள்:
- இந்த 4 விவரங்களுக்கு மட்டுமே கேக்கவும்
- அனைத்து 4 விவரங்களும் கிடைத்தால், நியமனத்தை உறுதிப்படுத்தவும்
- பொதுவான சுகாதார கேள்விகளுக்கு பதிலளிக்க வேண்டாம்
- நோயாளி அசம்பந்தமான கேள்வி கேட்டால், கூறுங்கள்: "நான் நியமனங்களை வாங்க மட்டுமே உதவ முடியும்।"
- கணிசமாக மற்றும் தொழிலாய மாற
- நியமனத்தை வாங்குவதற்கு முன் அனைத்து விவரங்களை உறுதிப்படுத்தவும்""",
        }

        return prompts.get(language, prompts["en"])

    async def _get_conversation_history(
        self, redis_client, session_id: str, max_messages: int = 10
    ) -> list:
        """Retrieve conversation history from Redis."""
        try:
            key = f"session:{session_id}:messages"
            messages_data = await redis_client.lrange(key, 0, max_messages - 1)

            history = []
            for msg_json in reversed(messages_data):
                try:
                    msg = json.loads(msg_json)
                    history.append({"role": msg.get("role"), "content": msg.get("content")})
                except:
                    pass

            return history[-10:]  # Return last 10 messages

        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []

    def _extract_action(self, response: str) -> Optional[str]:
        """Extract action from LLM response."""
        actions = ["book_appointment", "cancel_appointment", "reschedule_appointment", "check_status"]
        response_lower = response.lower()

        for action in actions:
            if action.replace("_", " ") in response_lower:
                return action

        return None

    async def _handle_agent_action(
        self,
        user_input: str,
        language: str,
        session_id: str,
        agent_response: str,
        action: Optional[str],
    ) -> Dict:
        """Handle appointment actions and generate final response."""
        if action == "book_appointment":
            return await self._handle_booking(user_input, language, session_id, agent_response)
        if action == "cancel_appointment":
            return await self._handle_cancel(user_input, language, session_id, agent_response)
        if action == "reschedule_appointment":
            return await self._handle_reschedule(user_input, language, session_id, agent_response)
        if action == "check_status":
            return await self._handle_check_status(user_input, language, session_id, agent_response)

        return {
            "message": agent_response,
            "action": action,
            "language": language,
            "model": settings.openai_model if settings.openai_api_key else settings.local_llm_backend,
        }

    async def _handle_booking(
        self, user_input: str, language: str, session_id: str, agent_response: str
    ) -> Dict:
        entities = self.entity_extractor.extract_entities(user_input)
        pending = await self.session_memory.merge_pending_booking(
            session_id,
            {
                "phone_number": entities.get("phone_number"),
                "date": entities.get("date"),
                "time": entities.get("time"),
                "doctor": entities.get("doctor_name") or entities.get("doctor_specialty"),
            },
        )

        phone_number = pending.get("phone_number") or ""
        doctor = pending.get("doctor") or "general physician"
        appointment_dt = parse_natural_datetime(pending.get("date"), pending.get("time"))
        state = await self.session_memory.get_state(session_id) or {}

        missing = []
        if not phone_number:
            missing.append(self._field_label(language, "phone"))
        if not pending.get("date"):
            missing.append(self._field_label(language, "date"))
        if not pending.get("time"):
            missing.append(self._field_label(language, "time"))
        if not pending.get("doctor"):
            missing.append(self._field_label(language, "doctor"))

        if missing:
            state["pending_booking"] = pending
            await self.session_memory.set_state(session_id, state)
            return {
                "message": self._msg(language, "missing_fields", fields=", ".join(missing)),
                "action": "book_appointment",
                "language": language,
            }

        if self._is_booking_confirmation(user_input) and state.get("last_appointment_id"):
            return {
                "message": self._msg(
                    language,
                    "already_booked",
                    doctor=doctor,
                    dt=appointment_dt.strftime("%Y-%m-%d %H:%M") if appointment_dt else "",
                    appt_id=state["last_appointment_id"],
                ),
                "action": "book_appointment",
                "language": language,
                "data": {"success": True, "appointment_id": state["last_appointment_id"]},
            }

        if not appointment_dt:
            return {
                "message": self._msg(language, "bad_datetime"),
                "action": "book_appointment",
                "language": language,
            }

        result = self.tools.book_appointment(
            phone_number=phone_number,
            doctor_name=doctor,
            appointment_datetime=appointment_dt,
            reason=agent_response,
            language=language,
        )
        if not result.get("success"):
            alt = result.get("alternatives", [])
            alt_text = ", ".join(alt) if alt else self._msg(language, "no_alternatives")
            state.pop("pending_booking", None)
            await self.session_memory.set_state(session_id, state)
            return {
                "message": self._msg(language, "conflict", alt_text=alt_text),
                "action": "book_appointment",
                "language": language,
                "data": result,
            }
        state.pop("pending_booking", None)
        state["last_appointment_id"] = result["appointment_id"]
        state["last_phone_number"] = phone_number
        await self.session_memory.set_state(session_id, state)

        booked_msg = self._msg(
            language,
            "booked",
            doctor=doctor,
            dt=appointment_dt.strftime("%Y-%m-%d %H:%M"),
            appt_id=result["appointment_id"],
        )
        return {
            "message": booked_msg,
            "action": "book_appointment",
            "language": language,
            "data": {**result, "success": True},
        }

    async def _resolve_appointment_id(
        self, session_id: str, entities: Dict
    ) -> Optional[int]:
        appointment_id = entities.get("appointment_id")
        if appointment_id:
            return appointment_id

        state = await self.session_memory.get_state(session_id) or {}
        if state.get("last_appointment_id"):
            return state["last_appointment_id"]

        phone = entities.get("phone_number") or state.get("last_phone_number")
        if phone:
            info = self.tools.find_appointment_by_phone(phone)
            if info.get("found"):
                return info["appointment_id"]
        return None

    def _is_action_completed(self, response: Dict) -> bool:
        data = response.get("data") or {}
        if data.get("success"):
            return True
        if response.get("action") in (
            "book_appointment",
            "reschedule_appointment",
            "cancel_appointment",
        ) and data.get("appointment_id"):
            return True
        return False

    async def _handle_cancel(
        self, user_input: str, language: str, session_id: str, agent_response: str
    ) -> Dict:
        entities = self.entity_extractor.extract_entities(user_input)
        appointment_id = await self._resolve_appointment_id(session_id, entities)
        if not appointment_id:
            return {
                "message": self._msg(language, "need_phone_cancel"),
                "action": "cancel_appointment",
                "language": language,
            }
        result = self.tools.cancel_appointment(appointment_id)
        if not result.get("success"):
            return {
                "message": self._msg(language, "not_found", appt_id=appointment_id),
                "action": "cancel_appointment",
                "language": language,
            }
        return {
            "message": self._msg(language, "cancelled", appt_id=appointment_id),
            "action": "cancel_appointment",
            "language": language,
            "data": {"appointment_id": appointment_id},
        }

    async def _handle_reschedule(
        self, user_input: str, language: str, session_id: str, agent_response: str
    ) -> Dict:
        entities = self.entity_extractor.extract_entities(user_input)
        state = await self.session_memory.get_state(session_id) or {}
        pending = await self.session_memory.merge_pending_reschedule(
            session_id,
            {
                "phone_number": entities.get("phone_number") or state.get("last_phone_number"),
                "date": entities.get("date"),
                "time": entities.get("time"),
                "appointment_id": entities.get("appointment_id"),
            },
        )

        appointment_dt = parse_natural_datetime(pending.get("date"), pending.get("time"))
        if not appointment_dt:
            return {
                "message": self._msg(language, "reschedule_need_datetime"),
                "action": "reschedule_appointment",
                "language": language,
            }

        resolve_entities = {
            "appointment_id": pending.get("appointment_id"),
            "phone_number": pending.get("phone_number"),
        }
        appointment_id = await self._resolve_appointment_id(session_id, resolve_entities)
        if not appointment_id:
            return {
                "message": self._msg(language, "reschedule_need_phone"),
                "action": "reschedule_appointment",
                "language": language,
            }

        result = self.tools.reschedule_appointment(appointment_id, appointment_dt)
        if not result.get("success"):
            alt_text = ", ".join(result.get("alternatives", [])) or self._msg(language, "no_alternatives")
            return {
                "message": self._msg(language, "reschedule_conflict", alt_text=alt_text),
                "action": "reschedule_appointment",
                "language": language,
            }

        state = await self.session_memory.get_state(session_id) or {}
        state.pop("pending_reschedule", None)
        state["last_appointment_id"] = appointment_id
        await self.session_memory.set_state(session_id, state)

        return {
            "message": self._msg(
                language,
                "rescheduled",
                appt_id=appointment_id,
                dt=appointment_dt.strftime("%Y-%m-%d %H:%M"),
            ),
            "action": "reschedule_appointment",
            "language": language,
            "data": {"success": True, "appointment_id": appointment_id, "new_date": appointment_dt.isoformat()},
        }

    async def _handle_check_status(
        self, user_input: str, language: str, session_id: str, agent_response: str
    ) -> Dict:
        entities = self.entity_extractor.extract_entities(user_input)
        appointment_id = await self._resolve_appointment_id(session_id, entities)
        if not appointment_id:
            return {
                "message": self._msg(language, "need_phone_status"),
                "action": "check_status",
                "language": language,
            }
        info = self.tools.get_appointment_status(appointment_id)
        if not info.get("found"):
            return {
                "message": self._msg(language, "not_found", appt_id=appointment_id),
                "action": "check_status",
                "language": language,
            }
        return {
            "message": self._msg(
                language,
                "status",
                appt_id=appointment_id,
                doctor=info["doctor_name"],
                status=info["status"],
                dt=info["appointment_date"][:16].replace("T", " "),
            ),
            "action": "check_status",
            "language": language,
            "data": {"success": True, "status": info["status"], "appointment_id": appointment_id},
        }

    async def _analyze_intent(self, user_input: str, language: str) -> str:
        """Analyze user intent using pattern matching (fallback)."""
        user_input_lower = user_input.lower()

        intents = {
            "book_appointment": ["appointment", "book", "schedule", "doctor", "visit"],
            "cancel_appointment": ["cancel", "remove", "delete", "postpone"],
            "check_status": ["status", "when", "confirm", "details"],
            "general_info": ["hello", "hi", "help", "info"],
        }

        for intent, keywords in intents.items():
            if any(keyword in user_input_lower for keyword in keywords):
                return intent

        return "general_info"

    async def _generate_response(
        self, intent: str, user_input: str, language: str
    ) -> Dict:
        """Generate response based on intent."""
        lower = user_input.lower()
        if any(
            phrase in lower
            for phrase in ("service", "provide", "what can you", "help with", "capabilities", "which services")
        ):
            services_msg = {
                "en": (
                    "I provide healthcare appointment services: book a new appointment, "
                    "reschedule an existing one, cancel a booking, or check appointment status. "
                    "Supported languages: English, Hindi, and Tamil. How would you like to proceed?"
                ),
                "hi": (
                    "मैं ये सेवाएँ देता हूँ: अपॉइंटमेंट बुक करना, पुनर्निर्धारण, रद्द करना, और स्थिति जाँचना। "
                    "भाषाएँ: अंग्रेज़ी, हिंदी, तमिल। आगे क्या करना है?"
                ),
                "ta": (
                    "நான் வழங்கும் சேவைகள்: நியமனம் பதிவு, மாற்றம், ரத்து, நிலை சரிபார்ப்பு. "
                    "மொழிகள்: ஆங்கிலம், ஹிந்தி, தமிழ். தொடர வேண்டுமா?"
                ),
            }
            return {
                "message": services_msg.get(language, services_msg["en"]),
                "action": None,
                "language": language,
            }

        responses = {
            "en": {
                "book_appointment": {
                    "message": "I can help you book an appointment. Please share doctor name, date, time, and your phone number.",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "I can help you cancel an appointment. Could you provide your appointment ID?",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "Let me check the status. Please provide your phone number or appointment ID.",
                    "action": "check_status",
                },
                "general_info": {
                    "message": "Hello! I can help you book, reschedule, or cancel your healthcare appointments. How can I assist you today?",
                    "action": None,
                },
            },
            "hi": {
                "book_appointment": {
                    "message": "मैं अपॉइंटमेंट बुक करने में मदद करूँगा। डॉक्टर, तारीख, समय और फ़ोन नंबर बताएं।",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "रद्द करने के लिए अपॉइंटमेंट ID बताएं।",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "स्थिति जांचने के लिए अपॉइंटमेंट ID या फ़ोन नंबर बताएं।",
                    "action": "check_status",
                },
            },
            "ta": {
                "book_appointment": {
                    "message": "நியமனம் பதிவு செய்ய உதவுகிறேன். மருத்துவர், தேதி, நேரம், தொலைபேசி எண் தரவும்.",
                    "action": "book_appointment",
                },
                "cancel_appointment": {
                    "message": "ரத்து செய்ய நியமன ID தரவும்.",
                    "action": "cancel_appointment",
                },
                "check_status": {
                    "message": "நிலைக்காக நியமன ID அல்லது தொலைபேசி எண் தரவும்.",
                    "action": "check_status",
                },
            },
        }

        default_responses = {
            "hi": {
                "message": "नमस्ते! मैं अपॉइंटमेंट बुक, रद्द या बदलने में मदद कर सकता हूँ।",
                "action": None,
            },
            "ta": {
                "message": "வணக்கம்! நியமனம் பதிவு, ரத்து அல்லது மாற்ற என்னால் உதவ முடியும்.",
                "action": None,
            },
        }

        language_responses = responses.get(language, {})
        intent_response = language_responses.get(
            intent, default_responses.get(language, responses["en"]["general_info"])
        )

        return {"message": intent_response.get("message"), "action": intent_response.get("action"), "language": language}

    async def _store_message(
        self, redis_client, session_id: str, role: str, content: str, language: str
    ):
        """Store message in Redis."""
        try:
            message = {
                "role": role,
                "content": content,
                "language": language,
                "timestamp": datetime.utcnow().isoformat(),
            }
            key = f"session:{session_id}:messages"
            await redis_client.lpush(key, json.dumps(message))
            await redis_client.expire(key, 86400)  # 24 hours

        except Exception as e:
            logger.error(f"Error storing message: {e}")

    def _get_error_message(self, language: str) -> str:
        return self._msg(language, "error")

    def _field_label(self, language: str, field: str) -> str:
        labels = {
            "en": {"phone": "phone number", "date": "date", "time": "time", "doctor": "doctor name"},
            "hi": {"phone": "फ़ोन नंबर", "date": "तारीख", "time": "समय", "doctor": "डॉक्टर का नाम"},
            "ta": {"phone": "தொலைபேசி எண்", "date": "தேதி", "time": "நேரம்", "doctor": "மருத்துவர் பெயர்"},
        }
        return labels.get(language, labels["en"]).get(field, field)

    def _msg(self, language: str, key: str, **kwargs) -> str:
        """Localized user-facing messages."""
        templates = {
            "en": {
                "error": "I'm having trouble processing that request. Could you repeat?",
                "missing_fields": "To book your appointment I still need: {fields}.",
                "bad_datetime": "I could not understand the date and time. Please say something like tomorrow at 10 AM.",
                "conflict": "That slot is already booked. Available slots are: {alt_text}",
                "no_alternatives": "No alternative slots are currently available.",
                "booked": "Your appointment with {doctor} is booked for {dt}. Appointment ID: {appt_id}",
                "already_booked": "Your appointment with {doctor} is already confirmed for {dt}. Appointment ID: {appt_id}",
                "cancelled": "Appointment {appt_id} has been cancelled successfully.",
                "not_found": "I could not find appointment {appt_id}. Please check the ID.",
                "reschedule_conflict": "Unable to reschedule to that time. Available alternatives: {alt_text}",
                "rescheduled": "Your appointment has been rescheduled to {dt}. Reference ID: {appt_id}",
                "reschedule_need_datetime": "What new date and time would you like for your appointment?",
                "reschedule_need_phone": "I could not find a recent appointment in this session. Please share the phone number you used when booking.",
                "need_phone_cancel": "Please share the phone number you used when booking so I can cancel your appointment.",
                "need_phone_status": "Please share the phone number you used when booking so I can check your appointment status.",
                "status": "Appointment {appt_id} with {doctor} is {status} on {dt}.",
            },
            "hi": {
                "error": "मुझे आपका अनुरोध समझने में समस्या हो रही है। कृपया दोहराएं?",
                "missing_fields": "अपॉइंटमेंट बुक करने के लिए मुझे ये जानकारी चाहिए: {fields}।",
                "bad_datetime": "मैं तारीख और समय समझ नहीं पाया। कृपया कल सुबह 10 बजे जैसा बताएं।",
                "conflict": "वह समय पहले से बुक है। उपलब्ध समय: {alt_text}",
                "no_alternatives": "कोई वैकल्पिक समय उपलब्ध नहीं है।",
                "booked": "आपकी {doctor} के साथ {dt} पर अपॉइंटमेंट बुक हो गई है। ID: {appt_id}",
                "cancelled": "अपॉइंटमेंट {appt_id} रद्द कर दी गई है।",
                "not_found": "अपॉइंटमेंट {appt_id} नहीं मिली।",
                "reschedule_conflict": "उस समय पर रीशेड्यूल नहीं हो सका। विकल्प: {alt_text}",
                "rescheduled": "आपकी अपॉइंटमेंट {dt} पर बदल दी गई है। ID: {appt_id}",
                "reschedule_need_datetime": "नई तारीख और समय बताएं।",
                "reschedule_need_phone": "इस सत्र में अपॉइंटमेंट नहीं मिली। बुकिंग वाला फ़ोन नंबर बताएं।",
                "need_phone_cancel": "रद्द करने के लिए बुकिंग वाला फ़ोन नंबर बताएं।",
                "need_phone_status": "स्थिति जांचने के लिए बुकिंग वाला फ़ोन नंबर बताएं।",
                "status": "अपॉइंटमेंट {appt_id}, {doctor}, स्थिति {status}, {dt}",
            },
            "ta": {
                "error": "உங்கள் கோரிக்கையை புரிந்து கொள்ள சிரமம். மீண்டும் சொல்லுங்களா?",
                "missing_fields": "நியமனம் பதிவு செய்ய இன்னும் தேவை: {fields}.",
                "bad_datetime": "தேதி மற்றும் நேரம் புரியவில்லை. நாளை காலை 10 மணி என்று சொல்லுங்கள்.",
                "conflict": "அந்த நேரம் ஏற்கனவே பதிவு செய்யப்பட்டுள்ளது. கிடைக்கும் நேரங்கள்: {alt_text}",
                "no_alternatives": "மாற்று நேரங்கள் இல்லை.",
                "booked": "{doctor} உடன் {dt} அன்று நியமனம் உறுதி. ID: {appt_id}",
                "cancelled": "நியமனம் {appt_id} ரத்து செய்யப்பட்டது.",
                "not_found": "நியமனம் {appt_id} கிடைக்கவில்லை.",
                "reschedule_conflict": "அந்த நேரத்தில் மாற்ற முடியவில்லை. மாற்றுகள்: {alt_text}",
                "rescheduled": "உங்கள் நியமனம் {dt} க்கு மாற்றப்பட்டது. ID: {appt_id}",
                "reschedule_need_datetime": "புதிய தேதி மற்றும் நேரம் சொல்லுங்கள்.",
                "reschedule_need_phone": "இந்த அமர்வில் நியமனம் கிடைக்கவில்லை. பதிவு செய்த தொலைபேசி எண் தரவும்.",
                "need_phone_cancel": "ரத்து செய்ய பதிவு செய்த தொலைபேசி எண் தரவும்.",
                "need_phone_status": "நிலைக்காக பதிவு செய்த தொலைபேசி எண் தரவும்.",
                "status": "நியமனம் {appt_id}, {doctor}, நிலை {status}, {dt}",
            },
        }
        lang_templates = templates.get(language, templates["en"])
        template = lang_templates.get(key, templates["en"].get(key, ""))
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
