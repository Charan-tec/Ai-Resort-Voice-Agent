import os
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # Security & Auth
    SECRET_KEY: str = Field(default="super-secret-resort-voice-agent-token-key-32chars")
    HMAC_ALGORITHM: str = Field(default="HS256")
    WEBHOOK_SIGNATURE_VERIFY: bool = Field(default=True)
    ALLOWED_ORIGINS: List[str] = Field(default=["*"])

    # Twilio Telephony
    TWILIO_ACCOUNT_SID: str = Field(default="AC_mock_twilio_account_sid")
    TWILIO_AUTH_TOKEN: str = Field(default="mock_twilio_auth_token")
    TWILIO_PHONE_NUMBER: str = Field(default="+18005551234")
    PUBLIC_BASE_URL: str = Field(default="https://voice.resort.example.com")

    # Exotel Telephony
    EXOTEL_API_KEY: Optional[str] = Field(default=None)
    EXOTEL_API_TOKEN: Optional[str] = Field(default=None)
    EXOTEL_ACCOUNT_SID: Optional[str] = Field(default=None)
    EXOTEL_SUBDOMAIN: Optional[str] = Field(default=None)
    EXOTEL_CALLER_ID: Optional[str] = Field(default=None)
    EXOTEL_PUBLIC_WSS_URL: Optional[str] = Field(default=None)

    # Database (PostgreSQL 16)
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/resort_voice")
    DATABASE_URL_SYNC: str = Field(default="postgresql://postgres:postgres@localhost:5432/resort_voice")
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)

    # Provider Selection
    LLM_PROVIDER: str = Field(default="openai")  # openai, gemini, google
    LLM_MODEL: str = Field(default="gpt-4o-mini")
    STT_PROVIDER: str = Field(default="assemblyai")  # assemblyai, deepgram, openai, google
    STT_MODEL: str = Field(default="universal-streaming")
    TTS_PROVIDER: str = Field(default="elevenlabs")  # elevenlabs, openai, azure
    TTS_MODEL: str = Field(default="eleven_flash_v2_5")
    TTS_VOICE_ID: str = Field(default="21m00Tcm4TlvDq8ikWAM")  # Rachel / Luxury concierge voice

    @field_validator("LLM_PROVIDER", mode="before")
    @classmethod
    def normalize_llm_provider(cls, v: str) -> str:
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in ("google", "gemini"):
                return "gemini"
            return clean
        return v

    @field_validator("LLM_MODEL", mode="before")
    @classmethod
    def normalize_llm_model(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("STT_PROVIDER", mode="before")
    @classmethod
    def normalize_stt_provider(cls, v: str) -> str:
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in ("assemblyai", "assembly", "aai"):
                return "assemblyai"
            return clean
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, v) -> List[str]:
        if isinstance(v, str):
            clean = v.strip()
            if not clean:
                return []
            if clean.startswith("[") and clean.endswith("]"):
                try:
                    import json
                    parsed = json.loads(clean)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in clean.split(",") if item.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        env = (self.ENVIRONMENT or "").strip().lower()
        if env == "production":
            insecure_fallbacks = {
                "super-secret-resort-voice-agent-token-key-32chars",
                "super-secret-development-key-for-voice-agent-32chars",
                "replace-with-a-very-long-and-secure-random-32char-secret",
                "mock_twilio_auth_token",
                "secret",
                "changeme",
                "password",
            }
            sec_key = (self.SECRET_KEY or "").strip()
            if not sec_key:
                raise ValueError(
                    "Production configuration requires an explicit, secure SECRET_KEY. "
                    "SECRET_KEY cannot be empty."
                )
            if (
                sec_key.lower() in insecure_fallbacks
                or "development" in sec_key.lower()
                or "dev-key" in sec_key.lower()
            ):
                raise ValueError(
                    "Production configuration requires an explicit secure SECRET_KEY instead of the insecure fallback. "
                    "Please configure a unique, high-entropy SECRET_KEY of at least 32 characters in production."
                )
            if len(sec_key) < 32:
                raise ValueError(
                    f"Production SECRET_KEY must be at least 32 characters long (received {len(sec_key)} characters)."
                )
            # Ensure production security behaviors are enforced
            self.WEBHOOK_SIGNATURE_VERIFY = True
            self.DEBUG = False
        return self

    # External API Keys
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    DEEPGRAM_API_KEY: Optional[str] = Field(default=None)
    ASSEMBLYAI_API_KEY: Optional[str] = Field(default=None)
    ASSEMBLY_API_KEY: Optional[str] = Field(default=None)
    AAI_API_KEY: Optional[str] = Field(default=None)
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GOOGLE_API_KEY: Optional[str] = Field(default=None)
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(default=None)
    AZURE_SPEECH_KEY: Optional[str] = Field(default=None)
    AZURE_SPEECH_REGION: Optional[str] = Field(default=None)

    @property
    def effective_gemini_api_key(self) -> Optional[str]:
        val = self.GEMINI_API_KEY or self.GOOGLE_API_KEY
        if val and isinstance(val, str):
            cleaned = val.strip()
            return cleaned if cleaned else None
        return None

    @property
    def effective_assemblyai_api_key(self) -> Optional[str]:
        val = (
            self.ASSEMBLYAI_API_KEY
            or self.ASSEMBLY_API_KEY
            or self.AAI_API_KEY
            or os.getenv("ASSEMBLYAI_API_KEY")
            or os.getenv("ASSEMBLY_API_KEY")
            or os.getenv("AAI_API_KEY")
            or os.getenv("STT_API_KEY")
        )
        if val and isinstance(val, str):
            cleaned = val.strip()
            return cleaned if cleaned else None
        return None

    @property
    def is_exotel_configured(self) -> bool:
        return bool(
            self.EXOTEL_API_KEY
            and self.EXOTEL_API_TOKEN
            and self.EXOTEL_ACCOUNT_SID
        )

    @property
    def effective_exotel_stream_url(self) -> str:
        if self.EXOTEL_PUBLIC_WSS_URL and self.EXOTEL_PUBLIC_WSS_URL.strip():
            return self.EXOTEL_PUBLIC_WSS_URL.strip()
        base = (self.PUBLIC_BASE_URL or "").strip().rstrip("/")
        ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
        return f"{ws_base}/ws/exotel-media"

    # Email Service
    EMAIL_PROVIDER: str = Field(default="sendgrid")  # sendgrid, ses, mock
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    AWS_SES_REGION: Optional[str] = Field(default="us-east-1")
    EMAIL_FROM: str = Field(default="reservations@azureparadise-resort.com")
    EMAIL_RETRY_MAX_ATTEMPTS: int = Field(default=5)
    EMAIL_RETRY_INITIAL_DELAY: float = Field(default=1.0)
    EMAIL_RETRY_MAX_DELAY: float = Field(default=30.0)

    # Audio & Streaming Pipeline Parameters
    SAMPLE_RATE: int = Field(default=8000)  # 8kHz telephony standard
    CHANNELS: int = Field(default=1)  # Mono
    FRAME_DURATION_MS: int = Field(default=20)  # 20ms frames
    BYTES_PER_FRAME_ULAW: int = Field(default=160)  # 8000 Hz * 0.02s * 1 byte/sample = 160 bytes
    BYTES_PER_FRAME_PCM: int = Field(default=320)  # 16-bit linear PCM = 320 bytes

    # VAD & EnergyGate Thresholds
    RMS_ENERGY_THRESHOLD: float = Field(default=450.0)  # Energy onset gate
    RMS_ENERGY_ALPHA: float = Field(default=0.95)  # Running noise baseline smoothing
    VAD_INTERRUPTION_FRAMES: int = Field(default=3)  # Consecutive frames to trigger barge-in (60ms)
    SILENCE_ENDPOINTING_MS: int = Field(default=1000)  # Silence to conclude user turn (1000ms for natural conversational pauses)

    # RAG Configuration
    VECTOR_DB_TYPE: str = Field(default="chroma")  # chroma, faiss
    CHROMA_PERSIST_DIR: str = Field(default="./data/chroma_db")
    RAG_TOP_K: int = Field(default=3)
    SPECULATIVE_PREFETCH_TTL_SECONDS: int = Field(default=15)
    SPECULATIVE_CACHE_MAX_ENTRIES: int = Field(default=100)

    # Circuit Breakers
    CIRCUIT_BREAKER_FAIL_THRESHOLD: int = Field(default=5)
    CIRCUIT_BREAKER_RESET_TIMEOUT_SEC: float = Field(default=30.0)


settings = Settings()
