from fastapi import APIRouter, HTTPException, Response
from services.tts_service import TextToSpeechService
from pydantic import BaseModel

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("/synthesize")
async def synthesize_tts(request: TTSRequest):
    """Synthesize text to WAV audio bytes."""
    tts = TextToSpeechService()
    try:
        audio_bytes = await tts.synthesize_async(request.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")
