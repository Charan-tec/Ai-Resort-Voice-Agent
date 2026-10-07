# System Architecture: Production Voice-to-Voice AI Agent for Luxury Resort

## 1. Executive Summary

This system implements a real-time, low-latency, voice-to-voice telephony AI agent designed for luxury resort reservations, guest concierge inquiries, and amenity bookings. 

The architecture enforces strict sub-second Time-to-First-Audio (TTFA) targets, resilient two-stage transactional booking safety backed by PostgreSQL 16 `btree_gist` exclusion constraints, and deterministic sub-200ms barge-in interruption handling.

---

## 2. End-to-End Pipeline Architecture

```mermaid
flowchart TD
    subgraph PSTN_Twilio ["Telephony Network"]
        UserPhone["Guest Phone"] <-->|"PSTN (8kHz μ-law)"| TwilioGateway["Twilio Voice Gateway"]
        TwilioGateway <-->|"Bidirectional WS /ws/media-stream\n20ms frames (160 bytes G.711u)"| AppWS["Twilio WebSocket Handler"]
    end

    subgraph AudioEngine ["Audio & Interruption Engine"]
        AppWS -->|"Inbound μ-law"| Codec["Audio Codec (8kHz μ-law <-> 16-bit Linear PCM)"]
        Codec -->|"Linear PCM"| EnergyGate["RMS EnergyGate\n(Interruption Detector)"]
        EnergyGate -->|"Interruption Event"| TurnMgr["TurnManager\n(State: LISTENING/THINKING/SPEAKING/BARGED_IN)"]
        Codec -->|"Streaming PCM"| STT["Streaming STT (Deepgram Nova-2 default)"]
        STT -->|"Interim Transcript"| Prefetch["Speculative RAG Prefetcher"]
        STT -->|"Final Transcript"| TurnMgr
    end

    subgraph LLMOrchestrator ["LLM & Function Execution"]
        TurnMgr -->|"User Prompt"| LLM["LLM Orchestrator (gpt-4o-mini streaming)"]
        LLM -->|"Tool Calls"| Registry["Tool Registry (Strictly 6 Tools)"]
        
        Registry -->|"1"| T1["check_availability()"]
        Registry -->|"2"| T2["calculate_price()"]
        Registry -->|"3"| T3["create_booking() -> PENDING HOLD (pending_token)"]
        Registry -->|"4"| T4["save_booking() -> CONFIRMED (Idempotent)"]
        Registry -->|"5"| T5["send_confirmation_email() -> Async Uniform Envelope"]
        Registry -->|"6"| T6["search_resort_knowledge()"]
        
        T6 -->|"Check Cache"| Cache[("Speculative TTL Cache")]
        Cache -->|"Miss"| Retriever["LangChain VectorStore Retriever"]
    end

    subgraph DatabaseLayer ["PostgreSQL 16 Persistence"]
        T1 & T3 & T4 --> DB[("PostgreSQL 16\nExtension: btree_gist\nExclusion: room_id + daterange")]
    end

    subgraph VoiceResponsePipeline ["Outbound Audio Pipeline"]
        LLM -->|"Streaming Tokens"| Chunker["Streaming Sentence Chunker (. ! ? :)"]
        Chunker -->|"Sentence Chunks"| TTS["Streaming TTS (ElevenLabs Flash ulaw_8000)"]
        TTS -->|"μ-law Audio"| Pacer["Outbound Pacer (20ms frames + Mark Tracking)"]
        Pacer -->|"Twilio media + mark payloads"| AppWS
    end

    subgraph BargeInInterruption ["Sub-200ms Interruption Flow"]
        EnergyGate -.->|"Interruption detected"| TurnMgr
        TurnMgr -.->|"1. Cancel LLM Task"| LLM
        TurnMgr -.->|"2. Cancel TTS Task"| TTS
        TurnMgr -.->|"3. Flush Audio Queue"| Pacer
        TurnMgr -.->|"4. Send 'clear' event"| AppWS
        TurnMgr -.->|"5. Truncate Assistant Transcript via Mark ACK"| TurnMgr
    end
```

---

## 3. Audio & Codec Specifications

- **Format**: G.711 μ-law (PCMU) at 8,000 Hz, 8-bit mono.
- **Packet Cadence**: 20 milliseconds per frame.
- **Frame Size**:
  - Encoded μ-law: 160 bytes.
  - Linear PCM (16-bit signed integer): 320 bytes.
- **Payload Format**: Base64-encoded strings wrapped in Twilio Media Stream JSON envelopes.

---

## 4. The Six Agent Tools

1. **`check_availability(room_type, check_in, check_out, guests)`**: Queries DB for unreserved rooms in range.
2. **`calculate_price(room_id, check_in, check_out, add_ons)`**: Computes subtotal, taxes (12%), resort fees ($45/night), and add-on costs.
3. **`create_booking(...)`**: Inserts a booking with status `pending`, generates a signed `pending_token` with 15-minute TTL.
4. **`save_booking(pending_token)`**: Idempotently commits the booking status from `pending` to `confirmed`.
5. **`send_confirmation_email(booking_id, customer_email)`**: Validates booking existence and customer email, returns uniform envelope `{"ok": bool, "data": ..., "spoken_hint": ...}`, enqueuing async delivery.
6. **`search_resort_knowledge(query, top_k)`**: Probes the speculative prefetch cache before executing LangChain vector retrieval.

---

## 5. Concurrency & Data Integrity

- **Database Engine**: PostgreSQL 16.
- **Extension**: `btree_gist`.
- **Constraint**:
  ```sql
  ALTER TABLE bookings ADD CONSTRAINT no_overlapping_bookings
  EXCLUDE USING gist (
      room_id WITH =,
      daterange(check_in, check_out, '[)') WITH &&
  )
  WHERE (status IN ('pending', 'confirmed'));
  ```
- Overlapping bookings for the same room raise SQLSTATE `23P01` (`exclusion_violation`).
