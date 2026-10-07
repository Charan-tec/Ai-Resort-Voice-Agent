import pytest
from app.tts.chunker import StreamingSentenceChunker


def test_chunker_basic_sentence_split():
    chunker = StreamingSentenceChunker(min_chunk_words=3)
    text = "Welcome to Azure Paradise Resort! How can I help you today?"
    tokens = text.split(" ")

    chunks = []
    for t in tokens:
        res = chunker.feed(t + " ")
        if res:
            chunks.extend(res)

    flushed = chunker.flush()
    if flushed:
        chunks.append(flushed)

    assert len(chunks) == 2
    assert "Welcome to Azure Paradise Resort!" in chunks[0]
    assert "How can I help you today?" in chunks[1]


def test_chunker_abbreviation_preservation():
    chunker = StreamingSentenceChunker(min_chunk_words=2)
    # Ensure "Mr. Smith" does not split after "Mr."
    chunker.feed("Good morning Mr. ")
    assert chunker.flush() == "Good morning Mr."


def test_chunker_flush_trailing_tokens():
    chunker = StreamingSentenceChunker(min_chunk_words=3)
    chunker.feed("We have available villas")
    chunks = chunker.feed(" for your requested dates")
    assert chunks == []  # No terminal punctuation yet

    flushed = chunker.flush()
    assert flushed == "We have available villas for your requested dates"
