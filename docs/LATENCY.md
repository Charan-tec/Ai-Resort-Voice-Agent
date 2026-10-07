# Latency Profile & Performance Benchmarks

## 1. Actual Measured Latencies

The following metrics were measured locally via `scripts/benchmark_latency.py` against the production pipeline components:

| Component | Metric | Measured Value | Architecture Target | Status |
|---|---|---|---|---|
| **RAG Speculative Cache** | Cache hit query lookup | **0.16 ms** | < 10 ms | PASS |
| **RAG Uncached Search** | LangChain vector store search (10 chunks) | **1,902.38 ms** (initial load) / ~25 ms (warm) | < 150 ms (warm) | PASS |
| **Tool: check_availability** | Date range query & room filter | **3.72 ms** | < 50 ms | PASS |
| **Tool: calculate_price** | Pricing calculations + tax breakdown | **0.31 ms** | < 20 ms | PASS |
| **Tool: create_booking** | Hold token generation & store insertion | **0.55 ms** | < 30 ms | PASS |
| **Tool: save_booking** | Idempotent token commit to confirmed | **0.36 ms** | < 30 ms | PASS |
| **Tool: send_confirmation_email**| Argument validation + background queue | **3.02 ms** | < 50 ms | PASS |
| **Tool: search_resort_knowledge**| Prefetch cache hit path | **0.39 ms** | < 10 ms | PASS |
| **EnergyGate Detection** | 3-frame (60ms) RMS energy computation | **0.252 ms** | < 2 ms | PASS |
| **Outbound Pacer Flush** | In-memory queue drain + Twilio CLEAR dispatch | **0.15 ms** | < 5 ms | PASS |
| **Sentence Chunker** | Streaming token punctuation segmentation | **0.069 ms** | < 1 ms | PASS |

---

## 2. End-to-End Latency Target Breakdown

### Path A: Turn with No Tool Execution (Casual conversational inquiry)
```
1. Customer finished speaking:
   - Speech endpointing (Deepgram VAD):           ~250 - 400 ms
2. LLM Time to First Token (gpt-4o-mini):         ~250 - 450 ms
3. Sentence Chunker (1st sentence boundary):       ~100 - 200 ms
4. TTS Time to First Audio Frame (ElevenLabs):     ~250 - 350 ms
5. Outbound Pacer transmission to Twilio:          ~20 ms
-------------------------------------------------------------------
Total No-Tool TTFA:                                0.87 - 1.42 seconds (Target: 0.9–1.45s)
```

### Path B: Turn with Tool & RAG Execution
```
1. Customer finished speaking (endpointing):       ~250 - 400 ms
2. LLM Tool Call Generation:                       ~300 - 450 ms
3. Tool Execution:
   - If search_resort_knowledge (Cache HIT):       ~0.16 - 0.40 ms
   - If check_availability / calculate_price:       ~0.50 - 4.00 ms
4. Follow-up LLM token generation:                 ~250 - 400 ms
5. Sentence Chunker + TTS TTFA:                    ~350 - 550 ms
6. Outbound Pacer transmission:                    ~20 ms
-------------------------------------------------------------------
Total With-Tool TTFA:                              1.17 - 1.80 seconds (Target: 1.4–2.05s)
```

### Path C: Real-Time Barge-In Interruption
```
1. Customer speaks while assistant is speaking:
   - EnergyGate sustained speech detection (3 frames):   60 ms
   - RMS computation time:                               0.25 ms
2. Orchestrator cancellation broadcast:                  0.10 ms
3. Pacer queue flush:                                    0.15 ms
4. Twilio CLEAR event transmission over WS:              ~15 - 30 ms
5. Twilio gateway playback buffer purge:                 ~40 - 60 ms
-------------------------------------------------------------------
Total Interruption Perception Latency:                   ~115 - 150 ms (Target: < 200 ms)
```
