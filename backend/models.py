from sqlalchemy import Column, String, DateTime, Integer, Boolean, Enum, Text
from datetime import datetime
from config.database import Base
import enum


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    name = Column(String)
    email = Column(String, nullable=True, index=True)
    language = Column(String, default="en")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, index=True)
    phone_number = Column(String, index=True)
    doctor_name = Column(String)
    appointment_date = Column(DateTime, index=True)
    reason = Column(Text)
    language = Column(String, default="en")
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    confirmation_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id = Column(String, primary_key=True, index=True)
    phone_number = Column(String, index=True)
    language = Column(String, default="en")
    session_data = Column(Text)  # JSON data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
