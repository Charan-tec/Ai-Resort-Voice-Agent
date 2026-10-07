import logging
import re
import sys
from typing import Any, Dict


# Regular expressions for PII redaction
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
AUTH_TOKEN_REGEX = re.compile(r"(Bearer\s+[A-Za-z0-9-_=]+|token=[\w\.-]+|api[-_]?key=[\w\.-]+)", re.IGNORECASE)


def redact_pii(text: str) -> str:
    """Scrub sensitive PII patterns from text."""
    if not isinstance(text, str):
        return text
    text = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    text = CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", text)
    text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
    text = AUTH_TOKEN_REGEX.sub("[REDACTED_TOKEN]", text)
    return text


class PIIRedactingFormatter(logging.Formatter):
    """Logging formatter that intercepts and scrubs PII from log output."""

    def format(self, record: logging.LogRecord) -> str:
        original_msg = super().format(record)
        return redact_pii(original_msg)


def setup_logger(name: str = "resort_voice_agent", level: str = "INFO") -> logging.Logger:
    """Configure structured logger with PII scrubbing."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        formatter = PIIRedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()
