import asyncio
import base64
import json
import time
from typing import Callable, Coroutine, Dict, List, Optional
from app.core.logging import logger
from app.telephony.codecs import ULAW_BYTES_PER_FRAME


class OutboundPacer:
    """
    Paces outbound 20ms μ-law audio frames to Twilio Media Stream over WebSocket.
    Manages mark events, delivery pacing (~20ms per packet), queue flushing on barge-in,
    and tracks acknowledged marks to know what audio the user actually heard.
    """

    def __init__(
        self,
        stream_sid: str,
        send_fn: Callable[[str], Coroutine],
        frame_interval_sec: float = 0.02,
        mark_interval_frames: int = 15,  # Insert mark event every 300ms
        on_playback_complete: Optional[Callable[[], None]] = None
    ):
        self.stream_sid = stream_sid
        self.send_fn = send_fn
        self.frame_interval_sec = frame_interval_sec
        self.mark_interval_frames = mark_interval_frames
        self.on_playback_complete = on_playback_complete

        self._queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        self._pacer_task: Optional[asyncio.Task] = None
        self._running = False

        # Mark tracking
        self._mark_counter = 0
        self._sent_marks: Dict[str, dict] = {}  # mark_name -> metadata
        self._last_acked_mark: Optional[str] = None
        self._last_acked_metadata: Optional[dict] = None
        self._frames_since_mark = 0
        self._turn_final_mark_sent = False
        self._active_turn_id = 1

    def start(self):
        """Start the background pacing loop."""
        if not self._running:
            self._running = True
            self._pacer_task = asyncio.create_task(self._pacing_loop())
            logger.info(f"OutboundPacer started for stream: {self.stream_sid}")

    def start_turn(self) -> int:
        """Explicitly begins a new assistant turn, advancing turn generation."""
        self._active_turn_id += 1
        self._turn_final_mark_sent = False
        return self._active_turn_id

    def mark_turn_end(self, turn_id: Optional[int] = None):
        """
        Signals that all audio chunks for the current assistant turn have been enqueued.
        Puts a turn_end sentinel in the queue so the pacing loop knows precisely
        when the true final audio packet of the whole turn has been delivered.
        """
        tid = self._active_turn_id if turn_id is None else turn_id
        self._queue.put_nowait({
            "type": "turn_end",
            "turn_id": tid
        })
        logger.debug(f"OutboundPacer: Enqueued turn_end sentinel (turn_id={tid}) for stream: {self.stream_sid}")

    async def enqueue_audio(self, ulaw_data: bytes, metadata: Optional[dict] = None):
        """Chunk raw μ-law audio into 160-byte 20ms frames and enqueue them."""
        total_len = len(ulaw_data)
        for offset in range(0, total_len, ULAW_BYTES_PER_FRAME):
            frame = ulaw_data[offset:offset + ULAW_BYTES_PER_FRAME]
            # Pad if needed to 160 bytes
            if len(frame) < ULAW_BYTES_PER_FRAME:
                frame = frame + b"\xff" * (ULAW_BYTES_PER_FRAME - len(frame))

            is_last = (offset + ULAW_BYTES_PER_FRAME >= total_len)
            await self._queue.put({
                "type": "audio",
                "data": frame,
                "metadata": metadata,
                "is_last": is_last
            })

    def handle_mark_ack(self, mark_name: str):
        """Called when Twilio sends back a 'mark' event."""
        self._last_acked_mark = mark_name
        if mark_name in self._sent_marks:
            self._last_acked_metadata = self._sent_marks[mark_name]
        logger.debug(f"Pacer: ACK received for mark: {mark_name}")

    def get_last_acked(self) -> tuple[Optional[str], Optional[dict]]:
        """Return the last acknowledged mark and its associated metadata."""
        return self._last_acked_mark, self._last_acked_metadata

    async def flush(self):
        """
        Immediately clear all queued audio frames and send Twilio 'clear' event.
        Used for sub-200ms barge-in interruption.
        """
        self._active_turn_id += 1  # Invalidate any in-flight or delayed turn_end sentinels
        self._turn_final_mark_sent = False
        self._frames_since_mark = 0
        dropped_frames = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                dropped_frames += 1
            except (asyncio.QueueEmpty, ValueError):
                break

        # Send Twilio clear event to flush Twilio's internal playback buffer
        clear_message = json.dumps({
            "event": "clear",
            "streamSid": self.stream_sid
        })
        try:
            await self.send_fn(clear_message)
            logger.info(
                f"OutboundPacer flushed {dropped_frames} frames & sent CLEAR for stream: {self.stream_sid}"
            )
        except Exception as exc:
            logger.error(f"Failed to send Twilio clear event: {exc}")

    async def reset(self):
        """Flush audio queue and reset all mark tracking state."""
        await self.flush()
        self._sent_marks.clear()
        self._last_acked_mark = None
        self._last_acked_metadata = None
        self._frames_since_mark = 0
        self._turn_final_mark_sent = False


    async def stop(self):
        """Stop pacer and cleanup."""
        self._running = False
        if self._pacer_task and not self._pacer_task.done():
            self._pacer_task.cancel()
            try:
                await self._pacer_task
            except asyncio.CancelledError:
                pass
        logger.info(f"OutboundPacer stopped for stream: {self.stream_sid}")

    async def _pacing_loop(self):
        """Core loop sending 20ms frames at 50Hz with accurate timing."""
        next_deadline = time.monotonic()

        while self._running:
            try:
                # Wait for next item in queue
                item = await self._queue.get()
                if item is None:
                    break

                if item["type"] == "audio":
                    frame_bytes = item["data"]
                    metadata = item.get("metadata") or {}
                    is_last = item.get("is_last", False)

                    payload = base64.b64encode(frame_bytes).decode("ascii")
                    media_message = json.dumps({
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {
                            "payload": payload
                        }
                    })
                    await self.send_fn(media_message)
                    self._frames_since_mark += 1

                    # Check if the next item in queue is the turn_end sentinel for active turn
                    is_turn_end_next = False
                    if not self._queue.empty():
                        next_item = self._queue._queue[0]
                        if (
                            next_item is not None
                            and next_item.get("type") == "turn_end"
                            and next_item.get("turn_id") == self._active_turn_id
                        ):
                            is_turn_end_next = True

                    # Interleave mark event periodically or at end of chunk
                    self._last_audio_metadata = metadata
                    if self._frames_since_mark >= self.mark_interval_frames or is_last:
                        self._mark_counter += 1
                        mark_name = f"mark_{self._mark_counter}"
                        is_final = bool(is_last and is_turn_end_next)
                        if is_final:
                            self._turn_final_mark_sent = True

                        self._sent_marks[mark_name] = {
                            **metadata,
                            "frame_count": self._frames_since_mark,
                            "is_last": is_last,
                            "is_final": is_final,
                            "sent_at": time.time()
                        }
                        mark_payload = {
                            "name": mark_name,
                            "is_last": is_last,
                            "is_final": is_final
                        }
                        if metadata.get("text"):
                            mark_payload["text"] = metadata["text"]
                        if metadata.get("tool_result"):
                            mark_payload["tool_result"] = metadata["tool_result"]

                        mark_msg = json.dumps({
                            "event": "mark",
                            "streamSid": self.stream_sid,
                            "mark": mark_payload
                        })
                        await self.send_fn(mark_msg)
                        self._frames_since_mark = 0

                        if is_final and self.on_playback_complete:
                            self.on_playback_complete()

                elif item["type"] == "turn_end":
                    sentinel_turn_id = item.get("turn_id")
                    # Ignore stale sentinels from turns that were flushed/interrupted
                    if sentinel_turn_id != self._active_turn_id:
                        logger.debug(
                            f"OutboundPacer: Ignored stale turn_end sentinel (turn_id={sentinel_turn_id}, active={self._active_turn_id})"
                        )
                    else:
                        if not self._turn_final_mark_sent:
                            self._mark_counter += 1
                            mark_name = f"mark_{self._mark_counter}"
                            self._sent_marks[mark_name] = {
                                "frame_count": self._frames_since_mark,
                                "is_last": True,
                                "is_final": True,
                                "sent_at": time.time()
                            }
                            mark_payload = {
                                "name": mark_name,
                                "is_last": True,
                                "is_final": True
                            }
                            last_meta = getattr(self, "_last_audio_metadata", None)
                            if last_meta and last_meta.get("text"):
                                mark_payload["text"] = last_meta["text"]
                            if last_meta and last_meta.get("tool_result"):
                                mark_payload["tool_result"] = last_meta["tool_result"]

                            mark_msg = json.dumps({
                                "event": "mark",
                                "streamSid": self.stream_sid,
                                "mark": mark_payload
                            })
                            await self.send_fn(mark_msg)
                            self._frames_since_mark = 0
                            if self.on_playback_complete:
                                self.on_playback_complete()

                        self._turn_final_mark_sent = False

                self._queue.task_done()

                # Sleep until next 20ms boundary
                next_deadline += self.frame_interval_sec
                delay = next_deadline - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    # Catch up if running slightly behind
                    next_deadline = time.monotonic()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Exception in outbound pacing loop: {exc}")
                await asyncio.sleep(0.01)
