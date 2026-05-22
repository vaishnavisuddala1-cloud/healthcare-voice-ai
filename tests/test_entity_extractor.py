import pytest
from agent.entity_extractor import EntityExtractor


def test_phone_number_extraction():
    """Test phone number extraction."""
    text = "My phone number is 555-123-4567"
    result = EntityExtractor.extract_phone_number(text)
    assert result is not None
    assert "555" in result


def test_email_extraction():
    """Test email extraction."""
    text = "Contact me at patient@example.com"
    result = EntityExtractor.extract_email(text)
    assert result == "patient@example.com"


def test_date_extraction():
    """Test date extraction."""
    text = "I want an appointment on 12/25/2024"
    result = EntityExtractor.extract_date(text)
    assert result is not None


def test_time_extraction():
    """Test time extraction."""
    text = "I prefer 2:30 PM"
    result = EntityExtractor.extract_time(text)
    assert result is not None
    assert "2" in result


def test_entity_extraction():
    """Test full entity extraction."""
    text = "My name is John, call me at 555-123-4567. Email: john@example.com. I want an appointment on tomorrow at 3:00 PM with a cardiologist"
    entities = EntityExtractor.extract_entities(text)

    assert entities["phone_number"] is not None
    assert entities["email"] == "john@example.com"
    assert entities["doctor_specialty"] == "cardiologist"
