# Engineering Assumptions & Architectural Trade-offs

## 1. Telephony & Protocol Standards
- **Twilio Media Streams**: Assumed standard Twilio bidirectional WebSocket streaming format with 8,000 Hz μ-law audio (`audio/x-mulaw`).
- **20ms Frame Invariant**: Inbound and outbound frames strictly adhere to 20ms duration (160 bytes of μ-law). Twilio rejects or buffers irregular packet bursts, necessitating a deterministic pacing loop (~50 frames/second).
- **Mark Event Precision**: Twilio `mark` events are interleaved into the outbound audio stream every ~250–500ms. Received mark acknowledgments reflect the exact timestamp of guest audio perception.

## 2. Audio Processing & Interruption
- **EnergyGate Tuning**: Ambient background noise on mobile PSTN channels is assumed at ~100–250 RMS. Speech onset is detected at RMS > 450 across 3 consecutive 20ms frames (60ms sustain) to avoid spurious false triggers caused by line clicks or breathing.
- **Barge-in Latency Budget**: The target interruption budget is <200ms from speech onset to client audio cutoff:
  - 60ms EnergyGate sustained detection
  - 20ms TurnManager state transition & cancellation broadcast
  - 20ms WebSocket `clear` event dispatch to Twilio
  - 50–80ms Twilio gateway playback buffer purge

## 3. Booking Lifecycle & Concurrency
- **Two-Stage Commit Pattern**: A booking must never jump directly from price quote to confirmed. The guest reserves a tentative room via `create_booking()`, creating a `pending` hold guarded by `pending_token` with a 15-minute expiration. `save_booking()` transitions the state to `confirmed`.
- **Database Invariant**: Concurrency safety relies on PostgreSQL 16 `btree_gist` exclusion constraints. No application-level locking (e.g. `SELECT FOR UPDATE` or Redis locks) can substitute for the ACID exclusion constraint at the database engine level.

## 4. LangChain RAG & Speculative Prefetch
- **Speculative Latency Optimization**: As guests speak, partial/interim STT transcripts are analyzed for intent keywords (e.g., "pool hours", "late checkout"). A background task queries the LangChain retriever and stores candidate answers in an in-memory cache with a 15-second TTL. When the LLM orchestrator invokes `search_resort_knowledge`, cache hits return in <10ms.

## 5. Security & Privacy
- **PII Redaction**: All logging pipelines must scrub customer emails, credit cards, and telephone numbers before writing to standard out or files.
- **Webhook Authenticity**: Webhooks must be verified using Twilio cryptographic signatures (`X-Twilio-Signature`). Media stream WebSocket connections require signed HMAC session tokens.
