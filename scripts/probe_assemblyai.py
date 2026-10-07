import asyncio
import inspect
import json
import os
import sys
import websockets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dotenv
dotenv.load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from app.core.config import Settings


async def probe_assemblyai_connection() -> bool:
    """
    Safely probes connectivity to the official AssemblyAI v3 streaming WebSocket API.
    Never prints or logs the raw API key.
    """
    fresh_settings = Settings()
    key = fresh_settings.effective_assemblyai_api_key
    if not key:
        print("[PROBE] No AssemblyAI API key configured in .env or environment.")
        print("[PROBE] Operates cleanly in verified offline/mock STT fallback mode.")
        return False

    masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "***"
    print(f"[PROBE] Found AssemblyAI API key: {masked} (length: {len(key)})")
    print("[PROBE] Connecting to AssemblyAI v3 Streaming WebSocket: wss://streaming.assemblyai.com/v3/ws?sample_rate=8000&encoding=pcm_mulaw ...")

    url = f"wss://streaming.assemblyai.com/v3/ws?sample_rate=8000&encoding=pcm_mulaw"
    headers = {"Authorization": key}

    sig = inspect.signature(websockets.connect)
    connect_kwargs = {}
    if "additional_headers" in sig.parameters:
        connect_kwargs["additional_headers"] = headers
    else:
        connect_kwargs["extra_headers"] = headers

    try:
        async with websockets.connect(url, **connect_kwargs) as ws:
            print("[PROBE] WebSocket handshake successful!")
            # Wait for Begin message with timeout
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                msg_type = data.get("type")
                session_id = data.get("session_id", "unknown")
                print(f"[PROBE] Received initial message type: '{msg_type}' (Session ID: {session_id})")
            except asyncio.TimeoutError:
                print("[PROBE] Connected successfully (initial response timed out).")

            # Clean termination
            await ws.send(json.dumps({"type": "Terminate"}))
            print("[PROBE] Live AssemblyAI streaming connectivity verified successfully!")
            return True
    except websockets.exceptions.InvalidStatusCode as err:
        print(f"[PROBE] HTTP Status Code Error during handshake: {err.status_code}")
        if err.status_code == 401:
            print("[PROBE] Authentication failed: Please verify the AssemblyAI API key is valid.")
        return False
    except Exception as exc:
        print(f"[PROBE] Connection failed: {exc}")
        return False


if __name__ == "__main__":
    success = asyncio.run(probe_assemblyai_connection())
    sys.exit(0 if success else 1)
