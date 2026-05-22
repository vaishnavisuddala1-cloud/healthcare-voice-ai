from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta

from scheduler.campaign_manager import CampaignManager
from backend.websocket_manager import manager

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
campaign_manager = CampaignManager()


class CampaignRequest(BaseModel):
    phone_number: str
    appointment_id: int
    session_id: str | None = None
    reminder_after_minutes: int = 0
    message: str = "Hello, this is a reminder about your appointment tomorrow."


@router.post("/reminder")
async def schedule_reminder(request: CampaignRequest):
    """Schedule an outbound reminder; optionally push to active WebSocket session."""
    try:
        send_at = datetime.utcnow() + timedelta(minutes=request.reminder_after_minutes)

        async def on_send(msg: str, lang: str):
            if request.session_id and request.session_id in manager.active_connections:
                await manager.send_outbound_campaign(request.session_id, msg, lang)

        campaign_manager.schedule_reminder(
            request.phone_number,
            request.appointment_id,
            send_at,
            request.message,
            on_send=on_send,
            language="en",
        )
        return {
            "status": "scheduled",
            "send_at": send_at.isoformat(),
            "websocket_push": request.session_id is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reminder/now")
async def send_reminder_now(request: CampaignRequest):
    """Immediately send outbound reminder to a connected WebSocket session."""
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id required for immediate push")
    await manager.send_outbound_campaign(
        request.session_id, request.message, language="en"
    )
    return {"status": "sent", "session_id": request.session_id}
