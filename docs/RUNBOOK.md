# Operations & Deployment Runbook

## 1. Local Development Setup

### Prerequisites
- Python 3.11 or 3.12
- PostgreSQL 16 (or automated local runner in `.pg16`)
- Optional: Twilio Account SID & Auth Token, Deepgram API Key, OpenAI API Key, ElevenLabs API Key

### Running Locally
1. Clone repository and install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. Configure `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Start the PostgreSQL 16 server (if not already running):
   ```powershell
   python scripts/setup_postgres.py
   ```
4. Run database migrations:
   ```powershell
   alembic upgrade head
   ```
5. Seed initial room inventory:
   ```powershell
   python -m app.db.seed
   ```
6. Start the voice agent FastAPI backend:
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
7. Verify health:
   ```powershell
   curl http://localhost:8000/health/ready
   ```

---

## 2. Running Automated Tests

Run the complete test suite:
```powershell
python -m pytest -v
```

Run only the mandatory PostgreSQL 16 concurrency test:
```powershell
python -m pytest tests/integration/test_postgres_concurrency.py -v
```

Run latency and performance benchmarks:
```powershell
python scripts/benchmark_latency.py
```

Run call simulator against local server:
```powershell
python scripts/simulate_call.py
```

---

## 3. Production Deployment with Docker Compose

1. Fill production secrets in `.env`:
   ```bash
   POSTGRES_PASSWORD=your_strong_db_password
   OPENAI_API_KEY=sk-...
   DEEPGRAM_API_KEY=...
   ELEVENLABS_API_KEY=...
   SECRET_KEY=generate_a_random_32_character_string
   ```
2. Launch stack (PostgreSQL 16, Backend, Caddy with automatic SSL):
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Check container logs:
   ```bash
   docker compose -f docker-compose.prod.yml logs -f backend
   ```

---

## 4. Twilio Telephony Integration

1. Point your Twilio Phone Number Voice Webhook to:
   `https://voice.resort.example.com/telephony/incoming-call` (HTTP POST).
2. The server generates signed TwiML instructing Twilio to open a Bidirectional Media Stream WebSocket to:
   `wss://voice.resort.example.com/ws/media-stream?token=<HMAC_SESSION_TOKEN>`.
3. Inbound audio begins streaming at 20ms G.711 μ-law frames.

---

## 5. Troubleshooting & FAQ

### PostgreSQL `btree_gist` Exclusion Error
If concurrent bookings attempt to reserve the same room for overlapping dates, PostgreSQL raises:
`IntegrityError: (psycopg2.errors.ExclusionViolation) conflicting key value violates exclusion constraint "no_overlapping_bookings"`
This is expected behavior ensuring data integrity. The orchestrator returns an availability failure hint to the guest.

### Interruption Sensitivity Tuning
If the assistant gets interrupted by quiet background clicks, raise `RMS_ENERGY_THRESHOLD` in `.env` (default is 450.0). If interruption requires too loud a voice, lower it to 350.0.
