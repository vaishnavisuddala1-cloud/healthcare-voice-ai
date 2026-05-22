import pytest
from agent.entity_extractor import EntityExtractor
from agent.intent_classifier import IntentClassifier, IntentType
from services.appointment_service import parse_natural_datetime


def test_date_does_not_become_appointment_id():
    text = "phone number is 7032256090, date is 23-06-2026, time at 2.pm, doctor with Dr.Sharma"
    entities = EntityExtractor.extract_entities(text)
    assert entities["appointment_id"] is None
    assert entities["phone_number"] == "7032256090"


def test_parse_short_year_date():
    dt = parse_natural_datetime("24-06-26", "2:00 PM")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 24
    assert dt.hour == 14


def test_details_message_is_booking_not_status():
    text = "phone number is 7032256090, date is 23-06-2026, time at 2.pm, doctor with Dr.Sharma"
    assert IntentClassifier.classify(text, "en") == IntentType.BOOK_APPOINTMENT


@pytest.mark.asyncio
async def test_status_check_after_pending_booking():
    from services.agent_v2 import HealthcareAgentV2

    agent = HealthcareAgentV2()
    sid = "status-after-pending"
    await agent.session_memory.set_state(
        sid,
        {
            "pending_booking": {
                "phone_number": "7032256090",
                "date": "24-06-26",
                "time": "2:00 PM",
                "doctor": "Dr Sharma",
            },
            "last_phone_number": "7032256090",
            "last_appointment_id": 17,
        },
    )
    r = await agent.process_input("Check the appointment Status", "en", sid)
    assert r.get("action") == "check_status"
    assert "conflict" not in (r.get("message") or "").lower()
    assert "7032256090" in r.get("message", "") or "17" in r.get("message", "") or "Dr Sharma" in r.get("message", "")
