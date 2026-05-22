import pytest
from agent.intent_classifier import IntentClassifier, IntentType


def test_intent_classification():
    """Test intent classification."""
    # Test booking appointment
    intent = IntentClassifier.classify("I want to book an appointment", "en")
    assert intent == IntentType.BOOK_APPOINTMENT

    # Test cancellation
    intent = IntentClassifier.classify("Cancel my appointment", "en")
    assert intent == IntentType.CANCEL_APPOINTMENT

    # Test status check
    intent = IntentClassifier.classify("What time is my appointment?", "en")
    assert intent == IntentType.CHECK_STATUS

    # Test symptom checker
    intent = IntentClassifier.classify("I have a fever and cough", "en")
    assert intent == IntentType.SYMPTOM_CHECKER


def test_spanish_intent_classification():
    """Test Spanish intent classification."""
    intent = IntentClassifier.classify("Quiero reservar una cita", "es")
    assert intent == IntentType.BOOK_APPOINTMENT


def test_intent_details():
    """Test getting intent details."""
    details = IntentClassifier.get_intent_details(IntentType.BOOK_APPOINTMENT)
    assert details["name"] == "Book Appointment"
    assert "date" in details["fields"]
