import base64
import logging
import time
from typing import Optional

from fastapi import WebSocket

from agent.dialogue_manager import DialogueManager
from services.agent_v2 import HealthcareAgentV2
from services.language_detection import LanguageDetectionService
from services.latency_tracker import LatencyTracker
from services.stt_service import WhisperSTTService
from services.tts_service import TextToSpeechService
from config.settings import settings

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: dict = {}
        self.stt_service = WhisperSTTService()
        self.agent = HealthcareAgentV2()
        self.dialogue_manager = DialogueManager()
        self.language_service = LanguageDetectionService()
        self.tts_service = TextToSpeechService()

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.dialogue_manager.create_conversation_state(session_id)
        await self.agent.session_memory.clear_flow_state(session_id)
        logger.info(f"Client {session_id} connected")

    async def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        await self.agent.session_memory.clear_flow_state(session_id)
        await self.dialogue_manager.end_conversation(session_id)
        logger.info(f"Client {session_id} disconnected")

    async def broadcast(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {e}")
                await self.disconnect(session_id)

    def _decode_audio(self, audio_data) -> bytes:
        if isinstance(audio_data, str):
            try:
                return base64.b64decode(audio_data)
            except Exception:
                return audio_data.encode("utf-8")
        return audio_data

    async def process_voice_turn(
        self, session_id: str, audio_data, language: str
    ) -> dict:
        """
        Full pipeline: STT → language detection → agent → TTS.
        Measures latency from speech-end (audio received) to first audio response.
        """
        tracker = LatencyTracker(session_id)
        speech_end = time.time()
        tracker.start_stage("speech_to_text")

        audio_bytes = self._decode_audio(audio_data)
        text = await self.stt_service.transcribe(audio_bytes, language)
        tracker.end_stage("speech_to_text")

        await self.broadcast(
            session_id,
            {"type": "transcription", "data": {"text": text, "language": language}},
        )

        tracker.start_stage("agent_reasoning")
        agent_response = await self.agent.process_input(
            text, language, session_id, respect_ui_language=True
        )
        tracker.end_stage("agent_reasoning")

        await self.dialogue_manager.process_dialogue_turn(session_id, text, agent_response)

        tracker.start_stage("text_to_speech")
        audio_out = await self.tts_service.synthesize_async(agent_response.get("message", ""))
        tracker.end_stage("text_to_speech")

        e2e_ms = (time.time() - speech_end) * 1000
        latency_report = tracker.get_report()
        latency_report["e2e_speech_to_audio_ms"] = e2e_ms
        latency_report["target_ms"] = settings.total_max_latency
        latency_report["within_target"] = e2e_ms <= settings.total_max_latency
        tracker.log_report(settings.total_max_latency)

        agent_response["latency_ms"] = round(e2e_ms, 2)
        agent_response["latency_breakdown"] = latency_report.get("stages", {})
        agent_response["e2e_speech_to_audio_ms"] = round(e2e_ms, 2)

        return {
            "type": "agent_response",
            "data": agent_response,
            "audio": base64.b64encode(audio_out).decode("utf-8") if audio_out else None,
        }

    async def process_text_turn(self, session_id: str, user_input: str, language: str) -> dict:
        """Text-only turn (no STT); still measures agent + TTS latency."""
        tracker = LatencyTracker(session_id)
        turn_start = time.time()

        tracker.start_stage("agent_reasoning")
        agent_response = await self.agent.process_input(
            user_input, language, session_id, respect_ui_language=True
        )
        tracker.end_stage("agent_reasoning")

        await self.dialogue_manager.process_dialogue_turn(session_id, user_input, agent_response)

        tracker.start_stage("text_to_speech")
        audio_out = await self.tts_service.synthesize_async(agent_response.get("message", ""))
        tracker.end_stage("text_to_speech")

        e2e_ms = (time.time() - turn_start) * 1000
        latency_report = tracker.get_report()
        latency_report["e2e_text_to_audio_ms"] = e2e_ms
        tracker.log_report(settings.total_max_latency)

        agent_response["latency_ms"] = round(e2e_ms, 2)
        agent_response["latency_breakdown"] = latency_report.get("stages", {})

        return {
            "type": "agent_response",
            "data": agent_response,
            "audio": base64.b64encode(audio_out).decode("utf-8") if audio_out else None,
        }

    async def send_outbound_campaign(
        self, session_id: str, message: str, language: str = "en"
    ):
        """Push proactive outbound message to a connected session."""
        tracker = LatencyTracker(f"campaign-{session_id}")
        tracker.start_stage("text_to_speech")
        audio_out = await self.tts_service.synthesize_async(message)
        tracker.end_stage("text_to_speech")
        await self.broadcast(
            session_id,
            {
                "type": "outbound_campaign",
                "data": {"message": message, "language": language},
                "audio": base64.b64encode(audio_out).decode("utf-8") if audio_out else None,
            },
        )


manager = WebSocketManager()
