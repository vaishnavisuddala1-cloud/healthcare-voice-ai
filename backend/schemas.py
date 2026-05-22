from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class PatientBase(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    language: str = "en"


class PatientCreate(PatientBase):
    pass


class Patient(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentBase(BaseModel):
    phone_number: str
    doctor_name: str
    appointment_date: datetime
    reason: str
    language: str = "en"


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    status: str
    confirmation_sent: Optional[bool] = None


class Appointment(AppointmentBase):
    id: int
    patient_id: Optional[int]
    status: str
    confirmation_sent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VoiceSessionBase(BaseModel):
    phone_number: str
    language: str = "en"


class VoiceSessionCreate(VoiceSessionBase):
    pass


class VoiceSession(VoiceSessionBase):
    id: str
    session_data: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class STTRequest(BaseModel):
    audio_data: bytes
    language: str = "en"


class STTResponse(BaseModel):
    text: str
    language: str
    confidence: float


class AgentRequest(BaseModel):
    user_input: str
    language: str = "en"
    session_id: str


class AgentResponse(BaseModel):
    response: str
    language: str
    action: Optional[str] = None
    data: Optional[dict] = None
