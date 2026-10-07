# Production Voice-to-Voice AI Agent for Luxury Resort

A low-latency, real-time voice-to-voice telephony AI agent designed for resort reservations, guest inquiries, and concierge services. Follows the authoritative architecture:

```
Customer (PSTN)
   ↓
Twilio Voice Gateway
   ↓
Bidirectional Media Stream (/ws/media-stream, 20ms μ-law frames)
   ↓
Streaming STT (Deepgram Nova-2 default) + VAD
   ↓
RMS EnergyGate + TurnManager (LISTENING, THINKING, SPEAKING, BARGED_IN)
   ↓
LLM Orchestrator (gpt-4o-mini streaming)
   ├── Exactly Six Agent Tools
   └── LangChain Speculative RAG (Chroma VectorStore + TTL Cache)
   ↓
Streaming Sentence Chunker (. ! ? :)
   ↓
Streaming TTS (ElevenLabs Flash ulaw_8000)
   ↓
Outbound 20ms Pacer (Twilio Mark Tracking & Clear Flush)
   ↓
Customer (Sub-200ms Barge-In Interruption Perception)
```

---

## Key Features

1. **Twilio Media Streams**: Real-time bidirectional streaming over WebSockets with 20ms G.711 μ-law audio frames (160 bytes).
2. **Sub-200ms Barge-In Interruption**:
   - `EnergyGate` calculates RMS on incoming 20ms frames.
   - Triggers `BARGED_IN` within 60ms of speech onset.
   - Instantly cancels LLM streaming and TTS synthesis.
   - Flushes outbound audio queue and dispatches Twilio `clear` event.
   - Truncates assistant transcript to only the words acknowledged by the caller's phone using Twilio `mark` tracking.
3. **Exact Six Agent Tools**:
   - `check_availability()`
   - `calculate_price()`
   - `create_booking()` (Stage 1: 15-minute tentative hold with `pending_token`)
   - `save_booking()` (Stage 2: Idempotent confirmation from pending to `confirmed`)
   - `send_confirmation_email()` (Pydantic validation, uniform envelope, background retry queue)
   - `search_resort_knowledge()` (Probes speculative prefetch cache before LangChain vector search)
4. **LangChain Speculative RAG**:
   - Ingestion: LangChain `RecursiveCharacterTextSplitter` and `Chroma` vector store.
   - Speculative Prefetch: Interim STT transcripts trigger background cache queries, yielding sub-millisecond retrieval (0.16 ms measured cache hit latency).
5. **PostgreSQL 16 `btree_gist` Exclusion Constraint**:
   - Implements `EXCLUDE USING gist (room_id WITH =, daterange(check_in, check_out, '[)') WITH &&) WHERE (status IN ('pending', 'confirmed'))`.
   - Guaranteed prevention of overlapping reservations at database engine level.
   - Concurrency tested against real PostgreSQL 16 server (`success_count == 1`, `failure_count == 1`).
6. **Security & Telemetry**:
   - Automatic PII redaction (scrubbing emails, phone numbers, credit cards).
   - HMAC session tokens and Twilio webhook signature verification.
   - Circuit breakers for all external services.

---

## Quickstart

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Configure Environment
```powershell
Copy-Item .env.example .env
```

### 3. Start PostgreSQL 16 & Run Migrations
```powershell
python scripts/setup_postgres.py
alembic upgrade head
python -m app.db.seed
```

### 4. Run Automated Tests
```powershell
python -m pytest -v
```

### 5. Run Concurrency Test
```powershell
python -m pytest tests/integration/test_postgres_concurrency.py -v
```

### 6. Run Latency Benchmark
```powershell
python scripts/benchmark_latency.py
```

### 7. Run Local Server
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Documentation Index

- [Architecture & Diagrams](file:///docs/ARCHITECTURE.md)
- [Voice Pipeline & Interruption Engineering](file:///docs/VOICE_PIPELINE.md)
- [Latency Profile & Benchmarks](file:///docs/LATENCY.md)
- [Operations & Runbook](file:///docs/RUNBOOK.md)
- [Engineering Assumptions](file:///docs/ASSUMPTIONS.md)
- [Architecture Gap Report](file:///docs/ARCHITECTURE_GAP_REPORT.md)
