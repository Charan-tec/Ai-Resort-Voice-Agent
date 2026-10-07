import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.audio.energy_gate import EnergyGate
from app.rag.prefetch import prefetch_cache
from app.rag.retriever import get_retriever
from app.telephony.codecs import pcm_to_ulaw
from app.telephony.pacer import OutboundPacer
from app.tools.tool_registry import tool_registry
from app.tts.chunker import StreamingSentenceChunker
import struct


async def benchmark_all():
    print("==================================================")
    print("REAL LATENCY & BENCHMARK INSTRUMENTATION")
    print("==================================================")

    results = {}

    # 1. RAG Uncached Latency
    retriever = get_retriever()
    t0 = time.perf_counter()
    docs = await retriever.aretrieve("What are the resort pool hours?", top_k=3)
    t1 = time.perf_counter()
    rag_uncached_ms = (t1 - t0) * 1000
    results["rag_uncached_ms"] = round(rag_uncached_ms, 2)
    print(f"RAG Uncached Query Latency: {rag_uncached_ms:.2f} ms")

    # 2. RAG Cached Latency (Speculative Cache)
    await prefetch_cache.set("what are the resort pool hours?", [{"content": docs[0].page_content if docs else "pool"}])
    t0 = time.perf_counter()
    cached_docs = await prefetch_cache.get("what are the resort pool hours?")
    t1 = time.perf_counter()
    rag_cached_ms = (t1 - t0) * 1000
    results["rag_cached_ms"] = round(rag_cached_ms, 2)
    print(f"RAG Speculative Cache Hit Latency: {rag_cached_ms:.2f} ms")

    # 3. Tool Latencies (All 6 tools)
    tool_benchmarks = {}

    t0 = time.perf_counter()
    await tool_registry.execute_tool("check_availability", {"check_in": "2026-10-01", "check_out": "2026-10-04"})
    t1 = time.perf_counter()
    tool_benchmarks["check_availability_ms"] = round((t1 - t0) * 1000, 2)

    t0 = time.perf_counter()
    price_res = await tool_registry.execute_tool("calculate_price", {"room_id": "villa-ocean-101", "check_in": "2026-10-01", "check_out": "2026-10-04"})
    t1 = time.perf_counter()
    tool_benchmarks["calculate_price_ms"] = round((t1 - t0) * 1000, 2)

    t0 = time.perf_counter()
    hold_res = await tool_registry.execute_tool("create_booking", {
        "room_id": "villa-ocean-101",
        "guest_name": "Latency Tester",
        "guest_email": "tester@example.com",
        "guest_phone": "+15550001111",
        "check_in": "2026-10-01",
        "check_out": "2026-10-04",
        "total_price": 1950.0
    })
    t1 = time.perf_counter()
    tool_benchmarks["create_booking_ms"] = round((t1 - t0) * 1000, 2)

    t0 = time.perf_counter()
    save_res = await tool_registry.execute_tool("save_booking", {"pending_token": hold_res["pending_token"]})
    t1 = time.perf_counter()
    tool_benchmarks["save_booking_ms"] = round((t1 - t0) * 1000, 2)

    t0 = time.perf_counter()
    await tool_registry.execute_tool("send_confirmation_email", {
        "booking_id": save_res["booking_id"],
        "customer_email": "tester@example.com"
    })
    t1 = time.perf_counter()
    tool_benchmarks["send_confirmation_email_ms"] = round((t1 - t0) * 1000, 2)

    t0 = time.perf_counter()
    await tool_registry.execute_tool("search_resort_knowledge", {"query": "pool hours", "top_k": 2})
    t1 = time.perf_counter()
    tool_benchmarks["search_resort_knowledge_ms"] = round((t1 - t0) * 1000, 2)

    results["tools"] = tool_benchmarks
    for name, dur in tool_benchmarks.items():
        print(f"Tool [{name}]: {dur:.2f} ms")

    # 4. EnergyGate Detection Latency (3 consecutive 20ms frames = 60ms)
    gate = EnergyGate(base_threshold=400.0, consecutive_frames=3)
    loud_pcm = struct.pack("<160h", *([5000 if i % 2 == 0 else -5000 for i in range(160)]))
    loud_ulaw = pcm_to_ulaw(loud_pcm)

    t0 = time.perf_counter()
    for _ in range(3):
        res = gate.process_frame(loud_ulaw, is_assistant_speaking=True)
    t1 = time.perf_counter()
    gate_detection_ms = (t1 - t0) * 1000
    results["energy_gate_calc_ms"] = round(gate_detection_ms, 3)
    print(f"EnergyGate 3-Frame Processing Latency: {gate_detection_ms:.3f} ms")

    # 5. Outbound Pacer Flush & Clear Latency
    sent_msgs = []
    async def dummy_send(m): sent_msgs.append(m)
    pacer = OutboundPacer(stream_sid="bench_stream", send_fn=dummy_send)
    await pacer.enqueue_audio(b"\xff" * 3200)

    t0 = time.perf_counter()
    await pacer.flush()
    t1 = time.perf_counter()
    flush_ms = (t1 - t0) * 1000
    results["pacer_flush_clear_ms"] = round(flush_ms, 2)
    print(f"Pacer Flush & Twilio CLEAR Latency: {flush_ms:.2f} ms")

    # 6. Sentence Chunker Token Segmentation Latency
    chunker = StreamingSentenceChunker(min_chunk_words=3)
    sentence_tokens = "The resort features a heated oceanfront infinity pool. How else can I assist?".split()
    t0 = time.perf_counter()
    for tok in sentence_tokens:
        chunker.feed(tok + " ")
    chunker.flush()
    t1 = time.perf_counter()
    chunker_ms = (t1 - t0) * 1000
    results["sentence_chunker_ms"] = round(chunker_ms, 3)
    print(f"Streaming Sentence Chunker Processing: {chunker_ms:.3f} ms")

    print("==================================================")
    print("Benchmark complete.")
    return results


if __name__ == "__main__":
    asyncio.run(benchmark_all())
