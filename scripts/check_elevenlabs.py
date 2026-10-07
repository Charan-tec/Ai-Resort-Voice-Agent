import asyncio
import os
import sys
import httpx
import dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
dotenv.load_dotenv(override=True)

from app.core.config import settings

async def check():
    key = settings.ELEVENLABS_API_KEY
    if not key:
        print("No key")
        return
    headers = {"xi-api-key": key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check user subscription status
        sub_resp = await client.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers)
        print("Subscription status code:", sub_resp.status_code, sub_resp.text)
        if sub_resp.status_code == 200:
            sub_data = sub_resp.json()
            tier = sub_data.get("tier")
            char_count = sub_data.get("character_count")
            char_limit = sub_data.get("character_limit")
            print(f"Tier: {tier}, Characters used: {char_count}/{char_limit}")

        # Check voices
        r = await client.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        print("Voices status code:", r.status_code, r.text)
        if r.status_code == 200:
            voices = r.json().get("voices", [])
            print(f"Total available voices: {len(voices)}")
            for v in voices:
                v_id = v.get("voice_id")
                name = v.get("name")
                cat = v.get("category")
                print(f"  Voice: {name} (ID: {v_id}, category: {cat})")

asyncio.run(check())
