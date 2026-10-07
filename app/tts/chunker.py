import re
from typing import AsyncGenerator, Generator, List, Optional


class StreamingSentenceChunker:
    """
    Splits streaming LLM text tokens into spoken sentence chunks at natural boundaries.
    Optimized for low-latency voice synthesis to achieve sub-second TTFA.
    """

    # Punctuation marks that signal sentence or clause completion
    SPLIT_REGEX = re.compile(r"([.!?:]+[\s\n]+)")
    # Common abbreviations to prevent premature splitting
    ABBREVIATIONS = {"mr.", "mrs.", "ms.", "dr.", "e.g.", "i.e.", "a.m.", "p.m.", "vs."}

    def __init__(self, min_chunk_words: int = 3):
        self.min_chunk_words = min_chunk_words
        self.buffer = ""

    def feed(self, token: str) -> List[str]:
        """Feed a new token and return complete sentences if a boundary was hit."""
        self.buffer += token
        chunks = []

        # Check if buffer contains candidate boundaries
        while True:
            match = self.SPLIT_REGEX.search(self.buffer)
            if not match:
                break

            split_pos = match.end()
            candidate = self.buffer[:split_pos].strip()

            # Check if candidate ends with an abbreviation
            last_word = candidate.split()[-1].lower() if candidate.split() else ""
            if last_word in self.ABBREVIATIONS:
                # Don't split on abbreviation, search after this match
                break

            # Ensure minimal length so we don't emit 1-word fragments
            words = candidate.split()
            if len(words) >= self.min_chunk_words:
                chunks.append(candidate)
                self.buffer = self.buffer[split_pos:]
            else:
                break

        return chunks

    def flush(self) -> Optional[str]:
        """Return any remaining text in the buffer when the LLM stream concludes."""
        remaining = self.buffer.strip()
        self.buffer = ""
        if remaining:
            return remaining
        return None
