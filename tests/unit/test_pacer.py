import asyncio
import json
import pytest
from app.telephony.pacer import OutboundPacer


@pytest.mark.asyncio
async def test_pacer_multi_chunk_with_deliberate_pause():
    """
    Tests:
    1. Chunk 1 is enqueued and paced to completion.
    2. While the queue is temporarily empty waiting for Chunk 2,
       is_final is FALSE and on_playback_complete is NOT called.
    3. Chunk 2 is enqueued after a deliberate pause, followed by mark_turn_end().
    4. Only upon finishing Chunk 2 is is_final=True emitted and on_playback_complete fired.
    """
    sent_messages = []
    playback_completed = False

    async def mock_send(msg: str):
        sent_messages.append(json.loads(msg))

    def on_complete():
        nonlocal playback_completed
        playback_completed = True

    pacer = OutboundPacer(
        stream_sid="MZ_test_multi_chunk",
        send_fn=mock_send,
        frame_interval_sec=0.005,  # 5ms pacing for fast unit testing
        mark_interval_frames=15,
        on_playback_complete=on_complete,
    )
    pacer.start()

    try:
        # Enqueue Chunk 1 (20 frames = 3200 bytes)
        chunk1 = b"\xff" * 3200
        await pacer.enqueue_audio(chunk1, metadata={"chunk": 1})

        # Wait for Chunk 1 to be completely sent and queue to become empty
        for _ in range(50):
            if pacer._queue.empty():
                break
            await asyncio.sleep(0.02)
        assert pacer._queue.empty(), "Queue should be empty after Chunk 1 is paced"

        # Check marks emitted so far
        marks_so_far = [m for m in sent_messages if m.get("event") == "mark"]
        assert len(marks_so_far) == 2, f"Expected 2 marks for Chunk 1 (periodic + chunk end), got {len(marks_so_far)}"

        # Periodic mark (frame 15)
        assert marks_so_far[0]["mark"]["name"] == "mark_1"
        assert marks_so_far[0]["mark"]["is_last"] is False
        assert marks_so_far[0]["mark"]["is_final"] is False

        # Chunk 1 end mark (frame 20)
        assert marks_so_far[1]["mark"]["name"] == "mark_2"
        assert marks_so_far[1]["mark"]["is_last"] is True
        # CRITICAL ASSERTION: is_final MUST BE FALSE despite empty queue!
        assert marks_so_far[1]["mark"]["is_final"] is False
        assert playback_completed is False, "on_playback_complete must NOT be called between chunks!"

        # Deliberate pause while queue is empty
        await asyncio.sleep(0.1)
        assert playback_completed is False

        # Now enqueue Chunk 2 (20 frames) and signal turn completion
        chunk2 = b"\x00" * 3200
        await pacer.enqueue_audio(chunk2, metadata={"chunk": 2})
        pacer.mark_turn_end()

        # Wait for Chunk 2 to be completely sent
        for _ in range(50):
            if pacer._queue.empty() and playback_completed:
                break
            await asyncio.sleep(0.02)

        all_marks = [m for m in sent_messages if m.get("event") == "mark"]
        assert len(all_marks) == 4, f"Expected 4 marks total, got {len(all_marks)}"

        # Mark 3: periodic in chunk 2
        assert all_marks[2]["mark"]["name"] == "mark_3"
        assert all_marks[2]["mark"]["is_last"] is False
        assert all_marks[2]["mark"]["is_final"] is False

        # Mark 4: final chunk and turn end
        assert all_marks[3]["mark"]["name"] == "mark_4"
        assert all_marks[3]["mark"]["is_last"] is True
        assert all_marks[3]["mark"]["is_final"] is True
        assert playback_completed is True, "on_playback_complete must be called upon final completion"

        # Total media frames sent: 40 frames
        media_frames = [m for m in sent_messages if m.get("event") == "media"]
        assert len(media_frames) == 40, f"Expected 40 media frames, got {len(media_frames)}"

    finally:
        await pacer.stop()


@pytest.mark.asyncio
async def test_pacer_barge_in_clears_turn_end_sentinel():
    """Verify barge-in flush drops queued audio and any turn_end sentinel without deadlocks."""
    sent_messages = []

    async def mock_send(msg: str):
        sent_messages.append(json.loads(msg))

    pacer = OutboundPacer(
        stream_sid="MZ_test_barge_in",
        send_fn=mock_send,
        frame_interval_sec=0.01,
        mark_interval_frames=15,
    )
    pacer.start()

    try:
        # Enqueue 40 frames and signal turn end
        await pacer.enqueue_audio(b"\xff" * 6400)
        pacer.mark_turn_end()

        # Immediately flush on barge-in
        await pacer.flush()

        # Check clear message sent
        clear_events = [m for m in sent_messages if m.get("event") == "clear"]
        assert len(clear_events) == 1
        assert pacer._queue.empty()
        assert pacer._turn_final_mark_sent is False

    finally:
        await pacer.stop()


@pytest.mark.asyncio
async def test_pacer_stale_turn_end_after_flush_is_ignored():
    """
    Regression test for cancellation racing with flush:
    1. Turn 1 enqueues audio and begins pacing.
    2. Barge-in flush executes, invalidating Turn 1.
    3. Delayed cancelled task injects a stale turn_end sentinel from Turn 1 after flush.
    4. Verify stale sentinel is safely discarded: no mark emitted, no on_playback_complete fired.
    5. Verify subsequent Turn 2 succeeds with accurate completion.
    """
    sent_messages = []
    completed_turns = []

    async def mock_send(msg: str):
        sent_messages.append(json.loads(msg))

    def on_complete():
        completed_turns.append(len(completed_turns) + 1)

    pacer = OutboundPacer(
        stream_sid="MZ_test_stale_sentinel",
        send_fn=mock_send,
        frame_interval_sec=0.005,
        mark_interval_frames=15,
        on_playback_complete=on_complete,
    )
    pacer.start()

    try:
        # Turn 1 begins
        turn1_id = pacer._active_turn_id
        await pacer.enqueue_audio(b"\xff" * 3200)

        # Barge-in flush occurs mid-turn
        await pacer.flush()
        assert pacer._active_turn_id > turn1_id, "Flush must advance active_turn_id"

        # Delayed task executes finally block after flush and calls mark_turn_end with old turn ID
        pacer.mark_turn_end(turn_id=turn1_id)

        # Wait to let pacing loop process queue
        await asyncio.sleep(0.05)

        # Verify no marks were emitted by the stale turn_end and on_playback_complete was NOT fired
        stale_marks = [m for m in sent_messages if m.get("event") == "mark" and m.get("mark", {}).get("is_final")]
        assert len(stale_marks) == 0, f"Stale sentinel must not emit final mark! Got: {stale_marks}"
        assert len(completed_turns) == 0, "on_playback_complete must NOT be called for interrupted turn!"

        # Turn 2 starts normally
        pacer.start_turn()
        await pacer.enqueue_audio(b"\x00" * 3200)
        pacer.mark_turn_end()

        # Wait for Turn 2 to finish
        for _ in range(50):
            if len(completed_turns) == 1 and pacer._queue.empty():
                break
            await asyncio.sleep(0.02)

        # Turn 2 must complete cleanly
        assert len(completed_turns) == 1, "Turn 2 must trigger exactly one playback completion"
        turn2_final_marks = [m for m in sent_messages if m.get("event") == "mark" and m.get("mark", {}).get("is_final")]
        assert len(turn2_final_marks) == 1, "Turn 2 must emit exactly one final mark"

    finally:
        await pacer.stop()
