import asyncio
from enum import Enum
import inspect
import time
from typing import Callable, Coroutine, List, Optional, Set
from app.core.logging import logger


class TurnState(str, Enum):
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    BARGED_IN = "BARGED_IN"
    INTERRUPTED = "INTERRUPTED"


class TurnManager:
    """
    Coordinates turn-taking state machine, turn ID assignment, deduplication,
    and barge-in interruption logic.
    Transitions:
      LISTENING -> (speech endpointed) -> THINKING
      THINKING -> (LLM token generation & TTS start) -> SPEAKING
      SPEAKING -> (EnergyGate voice onset) -> BARGED_IN -> (cancel & flush) -> LISTENING
      SPEAKING -> (TTS playback completed) -> LISTENING
    """

    def __init__(
        self,
        on_barge_in: Optional[Callable[[], Coroutine]] = None,
        on_user_turn_ready: Optional[Callable[..., Coroutine]] = None,
        session_id: Optional[str] = None
    ):
        self.state: TurnState = TurnState.LISTENING
        self.on_barge_in = on_barge_in
        self.on_user_turn_ready = on_user_turn_ready
        self.session_id = session_id

        self.last_state_change: float = time.monotonic()
        self.active_turn_id: int = 0
        self._lock = asyncio.Lock()

        # Turn lifecycle tracking & deduplication
        self.turn_counter: int = 0
        self.current_user_turn_id: Optional[str] = None
        self.last_interim_transcript: Optional[str] = None
        self.last_committed_transcript: Optional[str] = None
        self.last_committed_turn_id: Optional[str] = None
        self.last_committed_time: float = 0.0
        self.committed_turn_ids: Set[str] = set()

    def set_state(self, new_state: TurnState):
        logger.info(f"TurnManager: State transition [{self.state.value}] -> [{new_state.value}]")
        self.state = new_state
        self.last_state_change = time.monotonic()
        try:
            from app.orchestrator.broadcaster import event_broadcaster
            asyncio.create_task(event_broadcaster.notify_session_state(new_state.value))
        except Exception:
            pass

    def reset(self):
        """Reset turn state to LISTENING and turn counter/deduplication to initial state."""
        self.state = TurnState.LISTENING
        self.active_turn_id = 0
        self.turn_counter = 0
        self.last_state_change = time.monotonic()
        self.current_user_turn_id = None
        self.last_interim_transcript = None
        self.last_committed_transcript = None
        self.last_committed_turn_id = None
        self.last_committed_time = 0.0
        self.committed_turn_ids.clear()

    def is_speaking(self) -> bool:
        return self.state == TurnState.SPEAKING

    def is_listening(self) -> bool:
        return self.state == TurnState.LISTENING

    def start_user_turn(self) -> str:
        """Start a new user speech turn, assigning a unique turn_id."""
        if self.current_user_turn_id is None:
            self.turn_counter += 1
            self.current_user_turn_id = f"turn_user_{self.turn_counter}"
            logger.info(f"TURN START: {self.current_user_turn_id}")
        return self.current_user_turn_id

    def handle_user_speech_partial(self, transcript: str, turn_id: Optional[str] = None) -> Optional[str]:
        """
        Record and log an interim/partial transcript for the active turn.
        Returns active turn_id if changed, None if duplicate or empty.
        """
        text = transcript.strip()
        if not text:
            return None

        tid = turn_id or self.start_user_turn()
        if text == self.last_interim_transcript:
            return None

        self.last_interim_transcript = text
        logger.info(f"STT PARTIAL: {text}")
        return tid

    async def handle_user_speech_final(self, transcript: str, turn_id: Optional[str] = None) -> bool:
        """
        Commit a finalized user speech turn with deduplication and state validation.
        Returns True if the turn was accepted and committed, False if ignored.
        """
        async with self._lock:
            text = transcript.strip()
            if not text:
                return False

            tid = turn_id or self.current_user_turn_id or self.start_user_turn()
            logger.info(f"STT FINAL: {text}")

            # 1. Turn ID deduplication: ignore if this turn_id was already committed
            if tid in self.committed_turn_ids:
                logger.info(f"TURN DUPLICATE IGNORED: {tid}")
                return False

            # 2. Identical transcript deduplication (drop rapid duplicate echoes within 2.0s)
            now = time.monotonic()
            norm_new = text.lower().strip(".?!, ")
            if self.last_committed_transcript:
                norm_last = self.last_committed_transcript.lower().strip(".?!, ")
                time_since_last = now - self.last_committed_time

                if norm_new == norm_last and (time_since_last < 2.0 or self.state in (TurnState.THINKING, TurnState.SPEAKING)):
                    logger.info(f"TURN DUPLICATE IGNORED: {tid} (identical transcript within {time_since_last:.2f}s)")
                    return False

            # 3. State validation: if user speaks while assistant is SPEAKING, auto-trigger barge-in
            if self.state == TurnState.SPEAKING:
                logger.info(f"TurnManager: User speech finalized while SPEAKING -> Auto-initiating barge-in for turn {tid}")
                if self.on_barge_in:
                    await self.on_barge_in()
                self.set_state(TurnState.LISTENING)
            elif self.state == TurnState.THINKING:
                if (now - self.last_state_change) > 1.5:
                    logger.info(f"TurnManager: New user speech arrived while THINKING (>1.5s) -> Resetting to LISTENING for turn {tid}")
                    if self.on_barge_in:
                        await self.on_barge_in()
                    self.set_state(TurnState.LISTENING)
                else:
                    logger.info(f"TURN DUPLICATE IGNORED: {tid} (active thinking in progress)")
                    return False

            if self.state not in (TurnState.LISTENING, TurnState.BARGED_IN):
                logger.info(f"TURN DUPLICATE IGNORED: {tid} (state={self.state.value})")
                return False

            # Commit the turn
            self.committed_turn_ids.add(tid)
            self.last_committed_transcript = text
            self.last_committed_turn_id = tid
            self.last_committed_time = now
            self.current_user_turn_id = None
            self.last_interim_transcript = None

            self.set_state(TurnState.THINKING)
            self.active_turn_id += 1
            logger.info(f"TURN COMMITTED: {tid}")
            logger.info(f"ORCHESTRATOR PROCESSING: {tid}")

            if self.on_user_turn_ready:
                sig = inspect.signature(self.on_user_turn_ready)
                if len(sig.parameters) >= 2:
                    asyncio.create_task(self.on_user_turn_ready(text, tid))
                else:
                    asyncio.create_task(self.on_user_turn_ready(text))

            return True

    async def trigger_barge_in(self) -> bool:
        """
        Executed immediately when EnergyGate flags speech onset while assistant is SPEAKING.
        Returns True if barge-in was initiated.
        """
        async with self._lock:
            if self.state != TurnState.SPEAKING:
                return False

            logger.info("TurnManager: BARGE-IN INITIATED! Interrupting assistant turn.")
            self.set_state(TurnState.BARGED_IN)
            self.current_user_turn_id = None
            self.last_interim_transcript = None

            if self.on_barge_in:
                # Dispatch barge-in cancellation and audio clear
                await self.on_barge_in()

            self.set_state(TurnState.LISTENING)
            return True

    def on_tts_started(self):
        """Called when first synthesized audio packet starts playback."""
        if self.state in (TurnState.THINKING, TurnState.LISTENING):
            self.set_state(TurnState.SPEAKING)

    def on_tts_finished(self):
        """Called when assistant finishes speaking all queued sentences."""
        if self.state == TurnState.SPEAKING:
            self.set_state(TurnState.LISTENING)
