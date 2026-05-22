# System Architecture — 2Care.ai Voice AI Agent

## High-Level Pipeline

```mermaid
flowchart LR
    subgraph Client
        MIC[User Speech]
        WS[WebSocket Client]
        SPK[Audio Playback]
    end

    subgraph Backend["FastAPI Backend"]
        WSM[WebSocket Manager]
        STT[Whisper STT]
        LD[Language Detection]
        AG[LLM Agent]
        TOOLS[Tool Orchestration]
        TTS[Text-to-Speech]
        LAT[Latency Tracker]
    end

    subgraph Memory
        SM[Session Memory\nRedis TTL 24h]
        PM[Persistent Memory\nRedis TTL 7d]
    end

    subgraph Scheduling
        AE[Appointment Engine]
        DB[(PostgreSQL)]
    end

    subgraph Campaigns
        CM[Campaign Manager]
    end

    MIC --> WS
    WS --> WSM
    WSM --> STT
    STT --> LD
    LD --> AG
    AG --> SM
    AG --> PM
    AG --> TOOLS
    TOOLS --> AE
    AE --> DB
    AG --> TTS
    TTS --> LAT
    LAT --> WSM
    WSM --> SPK
    CM --> WSM
```

## Component Responsibilities

| Component | Role |
|-----------|------|
| **Whisper STT** | Converts voice input to text |
| **Language Detection** | Auto-detects English, Hindi, Tamil |
| **LLM Agent** | Interprets intent; drives dialogue |
| **Tool Orchestration** | `checkAvailability`, `book`, `cancel`, `reschedule` |
| **Appointment Engine** | Conflict detection, past-time validation, alternatives |
| **Session Memory** | Current conversation context (pending intent, slots) |
| **Persistent Memory** | Patient preferences, last doctor, preferred language |
| **Campaign Manager** | Outbound reminders via scheduled tasks + WebSocket push |
| **Latency Tracker** | Logs per-stage and end-to-end timings |

## Latency Measurement

End-to-end metric: **speech end → first audio response** (`e2e_speech_to_audio_ms`).

| Stage | Target (ms) |
|-------|-------------|
| Speech-to-text | ≤ 120 |
| Agent reasoning | ≤ 200 |
| Text-to-speech | ≤ 100 |
| **Total** | **< 450** |

Logs are written at `INFO` level with JSON breakdown per session.

## Memory Design

**Session memory** (`session:{id}:messages`, `session:{id}:state`)
- Short TTL (24 hours)
- Tracks multi-turn booking flow (doctor → date → time)

**Persistent memory** (`patient_context:{phone}`)
- Long TTL (7 days)
- Stores `preferred_language`, `last_doctor`, `preferred_hospital`

## Export Diagram for Submission

Open this file in VS Code / GitHub to render Mermaid, or export to PNG using [mermaid.live](https://mermaid.live).
