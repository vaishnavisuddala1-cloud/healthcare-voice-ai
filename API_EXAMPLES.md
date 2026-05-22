# API Usage Examples

## Basic Setup

```python
import asyncio
import websockets
import json
import base64

# WebSocket connection
async def connect_voice_session():
    uri = "ws://localhost:8000/ws/session-123"
    async with websockets.connect(uri) as websocket:
        # Send text input
        message = {
            "type": "text",
            "text": "I want to book an appointment",
            "language": "en"
        }
        await websocket.send(json.dumps(message))
        
        # Receive response
        response = await websocket.recv()
        print(json.loads(response))
```

## REST API Examples

### Using cURL

**Create Appointment:**
```bash
curl -X POST http://localhost:8000/api/appointments/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "555-123-4567",
    "doctor_name": "Dr. Johnson",
    "appointment_date": "2024-06-20T14:30:00",
    "reason": "Annual checkup",
    "language": "en"
  }'
```

**List Appointments:**
```bash
curl http://localhost:8000/api/appointments/?language=en
```

**Get Appointment:**
```bash
curl http://localhost:8000/api/appointments/1
```

**Update Appointment:**
```bash
curl -X PUT http://localhost:8000/api/appointments/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "confirmed"}'
```

## Python Examples

### Using httpx

```python
import httpx

async with httpx.AsyncClient() as client:
    # Create appointment
    response = await client.post(
        "http://localhost:8000/api/appointments/",
        json={
            "phone_number": "555-123-4567",
            "doctor_name": "Dr. Smith",
            "appointment_date": "2024-06-20T14:30:00",
            "reason": "Checkup",
            "language": "en"
        }
    )
    print(response.json())
```

### WebSocket with Audio

```python
import asyncio
import websockets
import json

async def send_audio_message():
    uri = "ws://localhost:8000/ws/session-456"
    async with websockets.connect(uri) as websocket:
        # Read audio file
        with open("sample_audio.wav", "rb") as f:
            audio_data = f.read()
        
        # Send audio for transcription
        message = {
            "type": "audio",
            "data": base64.b64encode(audio_data).decode(),
            "language": "es"
        }
        await websocket.send(json.dumps(message))
        
        # Get transcription
        response = await websocket.recv()
        print("Transcription:", json.loads(response))
        
        # Get agent response
        response = await websocket.recv()
        print("Agent:", json.loads(response))

asyncio.run(send_audio_message())
```

## Multilingual Examples

### Spanish

```bash
curl -X POST http://localhost:8000/api/appointments/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "555-987-6543",
    "doctor_name": "Dr. García",
    "appointment_date": "2024-06-21T10:00:00",
    "reason": "Consulta general",
    "language": "es"
  }'
```

### French

```bash
curl -X POST http://localhost:8000/api/appointments/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "555-456-7890",
    "doctor_name": "Dr. Dupont",
    "appointment_date": "2024-06-22T11:00:00",
    "reason": "Consultation générale",
    "language": "fr"
  }'
```

## Voice Conversation Flow

```
1. User connects to WebSocket
2. User sends voice (audio bytes)
3. Backend transcribes with Whisper
4. Backend classifies intent
5. Backend extracts entities
6. Backend stores in conversation memory
7. Backend generates response
8. Response sent back to user
9. Repeat for multi-turn conversation
```

## Error Handling

```python
import httpx

try:
    response = await client.post(
        "http://localhost:8000/api/appointments/",
        json=appointment_data,
        timeout=10.0
    )
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    print(f"Error {e.response.status_code}: {e.response.text}")
except httpx.RequestError as e:
    print(f"Connection error: {e}")
```

## Rate Limiting Recommendations

```python
# Implement rate limiting for production
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/appointments/")
@limiter.limit("10/minute")
async def create_appointment(request: Request, ...):
    pass
```
