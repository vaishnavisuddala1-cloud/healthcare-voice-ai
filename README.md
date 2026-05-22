# Real-Time Multilingual Voice AI Agent

Clinical appointment booking system for the [2Care.ai](http://2Care.ai) assignment — supports **English**, **Hindi**, and **Tamil** with real-time WebSocket voice, contextual memory, tool orchestration, and outbound campaigns.

## Features

- **Voice pipeline**: Speech → STT (Whisper) → Language detection → LLM agent → Tools → TTS → Audio
- **Appointment lifecycle**: Book, reschedule, cancel, availability check, conflict handling, alternatives
- **Session memory** (Redis, 24h): multi-turn conversation state
- **Persistent memory** (Redis, 7d): preferred language, last doctor, hospital
- **Outbound campaigns**: Scheduled reminders + immediate WebSocket push
- **Latency tracking**: End-to-end from speech-end to first audio; logged per stage

## Project Structure

```
voice-ai-agent/
├── backend/           # FastAPI, WebSocket, routes, campaigns
├── agent/             # Intent, entities, dialogue, tools/
├── memory/            # session_memory, persistent_memory
├── services/          # STT, TTS, agent, language detection, latency
├── scheduler/         # appointment_engine, campaign_manager
├── frontend/          # Web UI for voice demo
├── docs/              # Architecture diagram (SVG + Mermaid)
├── tests/
├── docker-compose.yml
└── requirements.txt
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 13+ (or Docker)
- Redis 7+ (or Docker)

### Local setup (Windows)

```powershell
cd voice-ai-agent
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # if present; otherwise edit .env
python init_db.py
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/app** for the voice demo UI.

### Docker

```bash
docker-compose up -d
```

## Configuration

```env
DATABASE_URL=postgresql://user:password@localhost:5432/voice_ai_db
REDIS_URL=redis://localhost:6379/0
WHISPER_MODEL=base
OPENAI_API_KEY=          # optional; uses pattern fallback if empty
SUPPORTED_LANGUAGES=en,hi,ta
DEFAULT_LANGUAGE=en
TOTAL_MAX_LATENCY=450
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (Mermaid) and [docs/architecture.svg](docs/architecture.svg) (submission diagram).

```
User Speech → WebSocket → STT → Language Detection → Agent → Tools → Scheduling
                              ↓                              ↓
                         Session Memory              Persistent Memory
                              ↓
                         TTS → Audio (<450ms target)
```

## Memory Design

| Layer | Storage | TTL | Example |
|-------|---------|-----|---------|
| Session | `session:{id}:messages` | 24h | Pending booking: cardiologist + tomorrow |
| Persistent | `patient_context:{phone}` | 7d | Prefers Hindi, last doctor Dr Sharma |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health |
| GET | `/health` | Detailed health |
| WS | `/ws/{session_id}` | Real-time voice/text |
| POST | `/api/appointments/` | Create appointment |
| POST | `/api/campaigns/reminder` | Schedule outbound reminder |
| POST | `/api/campaigns/reminder/now` | Push reminder to active WebSocket |
| POST | `/api/tts/synthesize` | TTS WAV bytes |

### WebSocket messages

**Send audio:**
```json
{ "type": "audio", "data": "<base64_wav>", "language": "en" }
```

**Send text:**
```json
{ "type": "text", "text": "Book appointment with cardiologist tomorrow", "language": "en" }
```

**Receive:**
```json
{
  "type": "agent_response",
  "data": { "message": "...", "latency_ms": 320, "latency_breakdown": {} },
  "audio": "<base64_wav>"
}
```

## Latency Breakdown

Measured in `services/latency_tracker.py` and attached to every agent response.

| Stage | Target |
|-------|--------|
| Speech-to-text | ≤ 120 ms |
| Agent reasoning | ≤ 200 ms |
| Text-to-speech | ≤ 100 ms |
| **E2E (speech end → first audio)** | **< 450 ms** |

Logs example:
```
INFO [demo-session] speech_to_text: 95.20ms
INFO [demo-session] agent_reasoning: 180.50ms
INFO [demo-session] text_to_speech: 85.00ms
INFO ✓ Total latency 360.70ms within target 450ms
```

**Note:** Whisper `base` on CPU often exceeds 120 ms STT alone. Use `tiny` model or GPU for production targets.

## Trade-offs

| Choice | Benefit | Cost |
|--------|---------|------|
| Whisper (local) | No API cost, privacy | Higher STT latency on CPU |
| Pattern fallback (no OpenAI key) | Works offline | Less flexible NLU |
| pyttsx3 TTS | Simple, local | Robotic voice; Windows-focused |
| Redis memory | Fast session/patient context | Requires Redis infra |
| Tool layer separate from agent | Testable scheduling | Extra indirection |

## Known Limitations

- Tamil/Hindi STT accuracy depends on Whisper model size
- pyttsx3 does not produce native-sounding Hindi/Tamil voices
- Telephony outbound (Twilio) not integrated — campaigns use WebSocket push
- Entity extraction uses regex; complex dates may need clarification
- PostgreSQL required for persistent appointments (no in-memory fallback)

## Testing

```bash
pytest tests/ -v
```

| Scenario | Command / Action |
|----------|------------------|
| Book appointment | Text: "Book cardiologist tomorrow 10am" + phone in message |
| Cancel | "Cancel appointment 123" |
| Reschedule | "Reschedule 123 to Friday 2pm" |
| Language | Select Hindi/Tamil in UI or speak in that language |
| Conflict | Book same doctor+slot twice |

## Submission Checklist

- [x] GitHub repository with full code
- [x] README (this file)
- [x] Architecture diagram: `docs/architecture.svg`
- [ ] Loom video (3 min): demo + architecture walkthrough

## License

MIT
