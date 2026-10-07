import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from app.core.config import settings
from app.core.logging import logger
from app.core.security import twilio_security, rate_limiter
from app.rag.ingest import build_vector_store
from app.services.email_worker import email_worker
from app.telephony.websocket import telephony_router
from app.telephony.exotel_websocket import exotel_router
from app.telephony.browser_websocket import browser_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start email worker and warm up RAG vector store
    logger.info("Initializing Resort Voice Agent backend...")
    email_worker.start()
    try:
        build_vector_store()
        logger.info("RAG vector store loaded successfully.")
    except Exception as exc:
        logger.warning(f"Could not build vector store on startup: {exc}")

    yield

    # Shutdown: gracefully stop workers
    logger.info("Shutting down Resort Voice Agent backend...")
    await email_worker.stop()


app = FastAPI(
    title="Resort AI Voice Agent API",
    version="1.0.0",
    description="Real-time voice-to-voice telephony AI agent for luxury resort reservations and concierge.",
    lifespan=lifespan
)

# CORS Configuration
# In production and per W3C specification, wildcard ('*') origins must NEVER be paired with allow_credentials=True.
cors_origins = [o.strip() for o in settings.ALLOWED_ORIGINS if o.strip()]
if "https://ai-resort-voice-agent.vercel.app" not in cors_origins:
    cors_origins.append("https://ai-resort-voice-agent.vercel.app")
has_wildcard = "*" in cors_origins

# Wildcard origins are not used with credentials. Credentials only enabled for explicit, non-wildcard origins.
allow_credentials = bool(cors_origins) and not has_wildcard

if settings.ENVIRONMENT == "production" and has_wildcard:
    logger.warning("CORS configured with wildcard origin '*' in production; credentials disabled for security.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Telephony & Browser Voice WebSockets
app.include_router(telephony_router)
app.include_router(exotel_router)
app.include_router(browser_router)


@app.get("/health/live", tags=["Health"])
async def liveness_probe():
    """Kubernetes / container liveness probe."""
    return {"status": "ok", "service": "resort-voice-agent"}


@app.get("/health/ready", tags=["Health"])
async def readiness_probe():
    """
    Readiness probe checking critical subsystems for real telephony calls.
    Reports provider configuration, Twilio readiness, and missing requirements without exposing secrets.
    """
    missing_requirements = []

    # Check Twilio credentials without exposing secret values
    twilio_account_sid_set = bool(
        settings.TWILIO_ACCOUNT_SID
        and not settings.TWILIO_ACCOUNT_SID.startswith("AC_mock")
        and not settings.TWILIO_ACCOUNT_SID.startswith("ACXXXX")
    )
    twilio_auth_token_set = bool(
        settings.TWILIO_AUTH_TOKEN
        and "mock" not in settings.TWILIO_AUTH_TOKEN.lower()
        and "your_" not in settings.TWILIO_AUTH_TOKEN.lower()
    )
    twilio_phone_set = bool(
        settings.TWILIO_PHONE_NUMBER
        and not settings.TWILIO_PHONE_NUMBER.startswith("+18005551234")
    )

    if not twilio_account_sid_set:
        missing_requirements.append("TWILIO_ACCOUNT_SID is missing or using default mock value.")
    if not twilio_auth_token_set:
        missing_requirements.append("TWILIO_AUTH_TOKEN is missing or using default mock value.")
    if not twilio_phone_set:
        missing_requirements.append("TWILIO_PHONE_NUMBER is missing or using default mock value.")

    # Check Public URL
    base_url = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    is_https = base_url.startswith("https://")
    is_localhost_or_example = any(h in base_url.lower() for h in ("localhost", "127.0.0.1", "0.0.0.0", "example.com"))
    public_url_ready = is_https and not is_localhost_or_example

    if not public_url_ready:
        missing_requirements.append(
            f"PUBLIC_BASE_URL ('{base_url}') must be a public HTTPS URL (e.g. ngrok or cloudflare tunnel) for Twilio to connect."
        )

    # Check AI Providers
    has_stt_key = bool(settings.effective_assemblyai_api_key) if settings.STT_PROVIDER == "assemblyai" else bool(settings.OPENAI_API_KEY)
    has_llm_key = bool(settings.effective_gemini_api_key) if settings.LLM_PROVIDER in ("gemini", "google") else bool(settings.OPENAI_API_KEY)
    has_tts_key = bool(settings.ELEVENLABS_API_KEY) if settings.TTS_PROVIDER == "elevenlabs" else bool(settings.OPENAI_API_KEY)

    if not has_stt_key:
        missing_requirements.append(f"STT provider '{settings.STT_PROVIDER}' API key is not configured.")
    if not has_llm_key:
        missing_requirements.append(f"LLM provider '{settings.LLM_PROVIDER}' API key is not configured.")
    if not has_tts_key:
        missing_requirements.append(f"TTS provider '{settings.TTS_PROVIDER}' API key is not configured.")

    ready_for_real_calls = (len(missing_requirements) == 0)

    # Check PostgreSQL Database connection
    db_connected = False
    try:
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db_sess:
            res = await db_sess.execute(text("SELECT 1"))
            db_connected = bool(res.scalar() == 1)
    except Exception:
        db_connected = False

    # Check RAG Vector Store
    rag_ready = False
    try:
        from app.rag.retriever import get_retriever
        retriever = get_retriever()
        rag_ready = retriever is not None
    except Exception:
        rag_ready = False

    return {
        "status": "ready" if ready_for_real_calls else "degraded",
        "ready_for_real_calls": ready_for_real_calls,
        "public_url": {
            "configured_base_url": base_url,
            "is_https": is_https,
            "is_public": not is_localhost_or_example,
        },
        "telephony": {
            "account_sid_configured": twilio_account_sid_set,
            "auth_token_configured": twilio_auth_token_set,
            "phone_number_configured": twilio_phone_set,
            "webhook_signature_verify": settings.WEBHOOK_SIGNATURE_VERIFY,
            "environment": settings.ENVIRONMENT,
            "exotel": {
                "configured": settings.is_exotel_configured,
                "account_sid_configured": bool(settings.EXOTEL_ACCOUNT_SID),
                "caller_id_configured": bool(settings.EXOTEL_CALLER_ID),
                "stream_url": settings.effective_exotel_stream_url,
            },
        },
        "providers": {
            "stt": {"provider": settings.STT_PROVIDER, "configured": has_stt_key, "status": "healthy" if has_stt_key else "unconfigured", "label": "AssemblyAI STT (v3 WebSocket)"},
            "llm": {"provider": settings.LLM_PROVIDER, "configured": has_llm_key, "status": "healthy" if has_llm_key else "unconfigured", "label": "Google Gemini LLM (Flash 2.5/3.6)"},
            "tts": {"provider": settings.TTS_PROVIDER, "configured": has_tts_key, "status": "healthy" if has_tts_key else "unconfigured", "label": "ElevenLabs TTS (Flash v2.5 μ-law)"},
            "rag": {"provider": settings.VECTOR_DB_TYPE, "configured": rag_ready, "status": "healthy" if rag_ready else "unconfigured", "label": "LangChain Chroma RAG"},
            "database": {"provider": "postgresql", "configured": db_connected, "status": "healthy" if db_connected else "unhealthy", "label": "PostgreSQL 16 DB"},
        },
        "missing_requirements": missing_requirements,
    }


@app.api_route("/telephony/incoming-call", methods=["GET", "POST"], tags=["Telephony"])
@app.api_route("/incoming-call", methods=["GET", "POST"], tags=["Telephony"])
async def incoming_call_webhook(request: Request):
    """
    Twilio voice webhook triggered when a customer dials the resort phone number.
    Returns TwiML instructing Twilio to open a Bidirectional Media Stream WebSocket.
    Supports both POST and GET, handles reverse proxies/tunnels, and validates signatures.
    """
    try:
        if request.method == "POST":
            form_data = await request.form()
            params = dict(form_data)
        else:
            params = dict(request.query_params)

        signature = request.headers.get("X-Twilio-Signature")
        raw_url = str(request.url)

        # Detect forwarded host/proto behind reverse proxies or tunnels (ngrok/Cloudflare/Caddy)
        forwarded_proto = request.headers.get("X-Forwarded-Proto") or request.headers.get("x-forwarded-proto") or ("https" if request.url.scheme == "https" else "http")
        forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get("x-forwarded-host") or request.headers.get("Host") or request.headers.get("host")

        # Determine expected public URL for signature validation and media stream
        configured_base = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
        expected_public_url = None
        if configured_base and not any(h in configured_base.lower() for h in ("localhost", "127.0.0.1", "example.com")):
            path = request.url.path
            query = f"?{request.url.query}" if request.url.query else ""
            expected_public_url = f"{configured_base}{path}{query}"
        elif forwarded_host and not any(h in forwarded_host.lower() for h in ("localhost", "127.0.0.1")):
            path = request.url.path
            query = f"?{request.url.query}" if request.url.query else ""
            expected_public_url = f"{forwarded_proto}://{forwarded_host}{path}{query}"

        # Signature validation when configured or in production
        if settings.WEBHOOK_SIGNATURE_VERIFY or settings.ENVIRONMENT == "production":
            is_valid = twilio_security.validate_webhook_signature(
                url=raw_url,
                params=params,
                signature=signature,
                expected_public_url=expected_public_url
            )
            if not is_valid:
                logger.warning("Rejected incoming call due to invalid Twilio signature.")
                return Response(content="Unauthorized Twilio Signature", status_code=403)

        call_sid = params.get("CallSid", "default_call")
        caller_number = params.get("From", "Unknown")
        logger.info(f"Incoming call received from {caller_number} (CallSid: {call_sid})")

        # Generate HMAC token for stream authentication
        token = twilio_security.generate_session_token(call_sid)

        # Build public wss:// URL (auto-fallback to forwarded public host if configured is localhost)
        active_base = configured_base
        if any(h in active_base.lower() for h in ("localhost", "127.0.0.1", "example.com")) and forwarded_host and not any(h in forwarded_host.lower() for h in ("localhost", "127.0.0.1")):
            active_base = f"{forwarded_proto}://{forwarded_host}"
            logger.info(f"Using forwarded host for media stream: {active_base}")

        ws_base = active_base.replace("https://", "wss://").replace("http://", "ws://")
        stream_url = f"{ws_base}/ws/media-stream?token={token}"

        vr = VoiceResponse()
        connect = Connect()
        stream = Stream(url=stream_url)
        stream.parameter(name="callSid", value=call_sid)
        stream.parameter(name="callerNumber", value=caller_number)
        connect.append(stream)
        vr.append(connect)

        return Response(content=str(vr), media_type="application/xml")

    except Exception as exc:
        logger.error(f"Error in incoming call webhook: {exc}", exc_info=True)
        fallback_vr = VoiceResponse()
        fallback_vr.say("We are experiencing technical difficulties. Please try again shortly.")
        fallback_vr.hangup()
        return Response(content=str(fallback_vr), media_type="application/xml", status_code=200)


# ------------------------------------------------------------------------------
# Dashboard & Recruiter Demo API Endpoints
# ------------------------------------------------------------------------------

@app.post("/api/exotel/call", tags=["Exotel Telephony"])
async def exotel_make_call(request: Request):
    """
    Trigger an outbound call using Exotel connecting to the bidirectional AgentStream WebSocket.
    Accepts JSON:
    - to / From: destination phone number
    - caller_id / CallerId: optional override for caller ID
    - stream_url / StreamUrl: optional override for AgentStream WSS URL
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    to_number = body.get("to") or body.get("From")
    if not to_number:
        return Response(content=json.dumps({"error": "'to' destination phone number is required."}), status_code=400, media_type="application/json")

    from app.services.exotel_service import exotel_service
    result = await exotel_service.initiate_outbound_call(
        to_phone=to_number,
        caller_id=body.get("caller_id") or body.get("CallerId"),
        stream_url=body.get("stream_url") or body.get("StreamUrl"),
        custom_field=body.get("custom_field"),
        status_callback=body.get("status_callback")
    )
    status_code = result.get("status_code", 200) if result.get("success") else result.get("status_code", 400)
    return Response(content=json.dumps(result), status_code=status_code, media_type="application/json")


@app.get("/api/agent/state", tags=["Agent"])
async def get_agent_state():
    """Returns current real-time agent state snapshot for the dashboard."""
    from app.orchestrator.broadcaster import event_broadcaster
    return event_broadcaster.get_snapshot()


@app.get("/api/bookings", tags=["Bookings"])
async def get_recent_bookings():
    """Returns recent resort bookings from database or active session."""
    bookings = []
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models import Booking
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        async with AsyncSessionLocal() as session:
            stmt = select(Booking).options(joinedload(Booking.customer), joinedload(Booking.room)).order_by(Booking.created_at.desc()).limit(10)
            result = await session.execute(stmt)
            db_bookings = result.scalars().all()
            for b in db_bookings:
                bookings.append({
                    "id": str(b.id),
                    "booking_code": b.booking_code,
                    "room_id": b.room_id,
                    "room_name": b.room.name if b.room else b.room_id,
                    "guest_name": b.customer.full_name if b.customer else "Guest",
                    "guest_email": b.customer.email if b.customer else None,
                    "check_in": str(b.check_in),
                    "check_out": str(b.check_out),
                    "guests": b.guests,
                    "status": b.status,
                    "total_price": b.total_price,
                    "currency": getattr(b, "currency", "USD") or "USD",
                    "pending_token": b.pending_token,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                })
    except Exception as exc:
        logger.debug(f"DB booking query exception: {exc}")

    from app.orchestrator.broadcaster import event_broadcaster
    active_b = event_broadcaster.state.get("active_booking")
    if active_b and not any(b.get("booking_code") == active_b.get("booking_code") for b in bookings):
        bookings.insert(0, active_b)

    return {"bookings": bookings}


@app.get("/api/pricing/currencies", tags=["Pricing"])
async def get_pricing_currencies():
    """Returns list of supported countries, currencies, and USD exchange rates."""
    from app.services.currency_service import currency_service
    return {
        "base_currency": "USD",
        "currencies": currency_service.get_supported_currencies(),
        "countries": currency_service.get_supported_countries()
    }


@app.get("/api/rooms", tags=["Rooms"])
async def get_rooms():
    """Returns resort rooms with base USD rates, images, amenities, and occupancy."""
    from app.tools.availability import RESORT_ROOMS
    rooms = []
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models import Room
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            stmt = select(Room).where(Room.is_active.is_(True)).order_by(Room.base_rate.desc())
            res = await session.execute(stmt)
            db_rooms = res.scalars().all()
            for r in db_rooms:
                rooms.append({
                    "room_id": r.id,
                    "name": r.name,
                    "room_type": r.room_type,
                    "max_occupancy": r.max_occupancy,
                    "base_rate_nightly": float(r.base_rate),
                    "amenities": r.amenities or []
                })
    except Exception as exc:
        logger.debug(f"Error querying rooms from database: {exc}")

    if not rooms:
        rooms = RESORT_ROOMS

    return {"rooms": rooms, "base_currency": "USD"}


@app.post("/api/pricing/calculate", tags=["Pricing"])
async def api_calculate_pricing(request: Request):
    """
    Dynamically converts USD room pricing into any international currency.
    Keeps database and internal calculation base prices strictly in USD.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    room_id = body.get("room_id", "villa-ocean-101")
    check_in = body.get("check_in", "2026-10-10")
    check_out = body.get("check_out", "2026-10-14")
    currency = (body.get("currency") or "USD").upper().strip()
    country = body.get("country", "US")
    add_ons = body.get("add_ons", [])

    from app.tools.pricing import calculate_price
    from app.services.currency_service import currency_service
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        calc_result = await calculate_price(
            room_id=room_id,
            check_in=check_in,
            check_out=check_out,
            add_ons=add_ons,
            db_session=session
        )

    if not calc_result.get("ok"):
        return Response(content=json.dumps(calc_result), status_code=400, media_type="application/json")

    # Base USD values
    subtotal_usd = calc_result.get("subtotal", 0.0)
    resort_fees_usd = calc_result.get("resort_fees", 0.0)
    taxes_usd = calc_result.get("taxes", 0.0)
    add_ons_usd = calc_result.get("add_ons_total", 0.0)
    total_usd = calc_result.get("total_price", 0.0)
    nightly_usd = calc_result.get("nightly_rate", 0.0)

    # Converted values
    converted_total = currency_service.convert_usd(total_usd, currency)
    converted_nightly = currency_service.convert_usd(nightly_usd, currency)
    converted_subtotal = currency_service.convert_usd(subtotal_usd, currency)
    converted_resort_fees = currency_service.convert_usd(resort_fees_usd, currency)
    converted_taxes = currency_service.convert_usd(taxes_usd, currency)
    converted_addons = currency_service.convert_usd(add_ons_usd, currency)

    return {
        "ok": True,
        "room_id": room_id,
        "room_name": calc_result.get("room_name"),
        "nights": calc_result.get("nights"),
        "country": country,
        "currency": currency,
        "exchange_rate": converted_total["exchange_rate"],
        "conversion_display": converted_total["conversion_display"],
        "base_pricing_usd": {
            "currency": "USD",
            "nightly_rate": nightly_usd,
            "subtotal": subtotal_usd,
            "resort_fees": resort_fees_usd,
            "taxes": taxes_usd,
            "add_ons_total": add_ons_usd,
            "total_price": total_usd,
        },
        "converted_pricing": {
            "currency": currency,
            "currency_name": converted_total["currency_name"],
            "currency_symbol": converted_total["currency_symbol"],
            "exchange_rate": converted_total["exchange_rate"],
            "nightly_rate": converted_nightly["converted_amount"],
            "nightly_formatted": converted_nightly["formatted"],
            "subtotal": converted_subtotal["converted_amount"],
            "subtotal_formatted": converted_subtotal["formatted"],
            "resort_fees": converted_resort_fees["converted_amount"],
            "resort_fees_formatted": converted_resort_fees["formatted"],
            "taxes": converted_taxes["converted_amount"],
            "taxes_formatted": converted_taxes["formatted"],
            "add_ons_total": converted_addons["converted_amount"],
            "add_ons_formatted": converted_addons["formatted"],
            "total_price": converted_total["converted_amount"],
            "total_formatted": converted_total["formatted"],
        },
        "spoken_hint": calc_result.get("spoken_hint")
    }


# Persistent session store for demo conversations
_DEMO_SESSIONS: dict = {}


@app.post("/api/demo/reset", tags=["Demo"])
async def reset_demo_session():
    """Reset active demo conversational sessions."""
    _DEMO_SESSIONS.clear()
    return {"status": "ok", "message": "Demo sessions reset successfully."}


@app.post("/api/conversation/clear", tags=["Conversation"])
async def clear_conversation():
    """
    Completely resets conversation state across all in-memory frontend/backend stores:
    1. EventBroadcaster state (conversation, current_tool, last_rag, active_booking, turns)
    2. _DEMO_SESSIONS in-memory cache
    3. Active browser voice sessions (SessionState messages & context slots, STT buffers, pacer queues)
    Strictly preserves PostgreSQL bookings, customer records, rooms, pricing, and RAG knowledge.
    Safe and idempotent when called multiple times.
    """
    from app.orchestrator.broadcaster import event_broadcaster
    from app.telephony.browser_websocket import clear_active_browser_sessions

    await event_broadcaster.clear_conversation()
    _DEMO_SESSIONS.clear()
    await clear_active_browser_sessions()

    return {
        "status": "ok",
        "message": "All conversation states, transcripts, and session buffers cleared successfully."
    }



@app.post("/api/demo/simulate-turn", tags=["Demo"])
async def simulate_demo_turn(request: Request):
    """
    Recruiter-demo action: Simulates a guest inquiry turn through the real Gemini LLM,
    tools (check_availability, calculate_price, RAG), and ElevenLabs TTS pipeline.
    Maintains conversational context across multi-turn dialogs.
    """
    body = await request.json()
    user_prompt = body.get("prompt", "What room types do you offer?")
    session_id = body.get("session_id", "default_demo")
    reset_session = body.get("reset", False)

    from app.orchestrator.broadcaster import event_broadcaster
    from app.tools.tool_registry import tool_registry
    from app.llm.gemini import GeminiLLMProvider
    from app.llm.openai import OpenAILLMProvider
    from app.db.session import AsyncSessionLocal
    from app.orchestrator.session import SessionState

    await event_broadcaster.notify_session_state("THINKING")
    await event_broadcaster.notify_user_transcript(user_prompt, is_final=True)

    if reset_session or session_id not in _DEMO_SESSIONS:
        _DEMO_SESSIONS[session_id] = SessionState(call_sid=session_id, stream_sid=session_id)

    session = _DEMO_SESSIONS[session_id]
    session.add_user_message(user_prompt)

    llm = GeminiLLMProvider() if settings.LLM_PROVIDER in ("gemini", "google") else OpenAILLMProvider()
    tools = tool_registry.get_tool_definitions()

    response_tokens = []
    pending_tools = []
    tool_results = []
    last_tool_res = None

    try:
        async for event in llm.stream_chat(session.messages, tools=tools):
            if event["type"] == "token":
                response_tokens.append(event["content"])
            elif event["type"] == "tool_call":
                pending_tools.append(event)

        if pending_tools:
            async with AsyncSessionLocal() as db_session:
                for tc in pending_tools:
                    t_name = tc["name"]
                    t_args = tc["arguments"]
                    await event_broadcaster.notify_tool_call(t_name, t_args, None, "executing")
                    res = await tool_registry.execute_tool(t_name, t_args, db_session=db_session)
                    last_tool_res = res
                    session.update_context_from_tool(t_name, t_args, res)
                    tool_results.append({"name": t_name, "args": t_args, "result": res})
                    await event_broadcaster.notify_tool_call(t_name, t_args, res, "completed")
                    if isinstance(res, dict) and ("booking_id" in res or "pending_token" in res or "booking_code" in res or "total_price" in res):
                        await event_broadcaster.notify_booking_update(res)

                    session.messages.append({
                        "role": "function",
                        "name": t_name,
                        "content": json.dumps(res) if isinstance(res, dict) else str(res)
                    })

            async for event in llm.stream_chat(session.messages, tools=None):
                if event["type"] == "token":
                    response_tokens.append(event["content"])

        full_reply = "".join(response_tokens).strip()

        # Fallback to spoken hint if LLM returned nothing after tool execution
        if not full_reply and last_tool_res and isinstance(last_tool_res, dict) and last_tool_res.get("spoken_hint"):
            full_reply = last_tool_res["spoken_hint"]

        if not full_reply:
            full_reply = "I would be happy to assist you with our rooms, pricing, amenities, or reservations. How may I help you today?"

        session.complete_assistant_turn(full_reply)
        await event_broadcaster.notify_session_state("SPEAKING")
        await event_broadcaster.notify_agent_response(full_reply, is_final=True)
        await event_broadcaster.notify_session_state("LISTENING")

        return {
            "user_prompt": user_prompt,
            "agent_response": full_reply,
            "tool_calls": tool_results,
            "session_state": "LISTENING"
        }
    except Exception as exc:
        logger.error(f"Demo simulation error: {exc}", exc_info=True)
        await event_broadcaster.notify_session_state("LISTENING")
        return {"error": str(exc), "session_state": "LISTENING"}


# Mount built frontend single-page application when available
from fastapi.staticfiles import StaticFiles
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

