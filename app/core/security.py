import hmac
import hashlib
import time
from typing import Dict, Optional
from twilio.request_validator import RequestValidator
from app.core.config import settings
from app.core.logging import logger


class TwilioSecurity:
    """Security verification for Twilio webhooks and Media Stream sessions."""

    def __init__(self, auth_token: str, secret_key: str):
        self.auth_token = auth_token
        self.secret_key = secret_key
        self.validator = RequestValidator(auth_token)

    def validate_webhook_signature(
        self,
        url: str,
        params: Dict[str, str],
        signature: Optional[str],
        expected_public_url: Optional[str] = None
    ) -> bool:
        """Validate that an incoming HTTP request originated from Twilio."""
        if not settings.WEBHOOK_SIGNATURE_VERIFY:
            return True
        if not signature:
            logger.warning("Missing X-Twilio-Signature header on webhook request.")
            return False

        # 1. Attempt validation using the direct request URL
        if self.validator.validate(url, params, signature):
            return True

        # 2. If behind reverse proxy or tunnel, try validating against expected public URL
        if expected_public_url and expected_public_url != url:
            if self.validator.validate(expected_public_url, params, signature):
                logger.debug(f"Twilio signature validated using expected public URL: {expected_public_url}")
                return True

        # Diagnostic logging without exposing secret values
        checked_urls = [url]
        if expected_public_url and expected_public_url != url:
            checked_urls.append(expected_public_url)
        logger.warning(
            f"Invalid Twilio signature. Checked URLs: {checked_urls}. "
            f"Parameter keys received: {list(params.keys())}. "
            "Verify that TWILIO_AUTH_TOKEN matches your Twilio Console credentials."
        )
        return False

    def generate_session_token(self, call_sid: str, timestamp: Optional[int] = None) -> str:
        """Generate a cryptographically signed HMAC token for WebSocket session security."""
        ts = timestamp or int(time.time())
        message = f"{call_sid}:{ts}".encode("utf-8")
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message,
            hashlib.sha256
        ).hexdigest()
        return f"{call_sid}:{ts}:{signature}"

    def verify_session_token(self, token: str, max_age_seconds: int = 3600) -> Optional[str]:
        """Verify the HMAC session token and ensure it has not expired. Returns call_sid if valid."""
        try:
            parts = token.split(":")
            if len(parts) != 3:
                return None
            call_sid, ts_str, signature = parts
            ts = int(ts_str)

            now = int(time.time())
            if abs(now - ts) > max_age_seconds:
                logger.warning(f"Expired session token for CallSid: {call_sid}")
                return None

            expected_message = f"{call_sid}:{ts}".encode("utf-8")
            expected_signature = hmac.new(
                self.secret_key.encode("utf-8"),
                expected_message,
                hashlib.sha256
            ).hexdigest()

            if hmac.compare_digest(signature, expected_signature):
                return call_sid
            return None
        except Exception as exc:
            logger.error(f"Error verifying session token: {exc}")
            return None


class RateLimiter:
    """In-memory sliding window rate limiter for connection protection."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = self.requests.get(client_id, [])
        # Filter out timestamps outside window
        timestamps = [ts for ts in timestamps if ts > window_start]

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        self.requests[client_id] = timestamps
        return True


twilio_security = TwilioSecurity(
    auth_token=settings.TWILIO_AUTH_TOKEN,
    secret_key=settings.SECRET_KEY
)

rate_limiter = RateLimiter(max_requests=100, window_seconds=60.0)
