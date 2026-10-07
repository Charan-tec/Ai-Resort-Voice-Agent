# Twilio Voice Inbound Call Setup Guide

This guide walks you through connecting a real telephone call to your Resort AI Voice Agent via Twilio Voice and Bidirectional Media Streams.

---

## Architecture Overview

```
Customer Cellphone 
       │
       ▼ (PSTN Call)
 Twilio Voice Cloud
       │
       ├─► HTTP POST /telephony/incoming-call (Webhook)
       │    └── Returns TwiML: <Connect><Stream url="wss://<tunnel>/ws/media-stream?token=...">
       │
       └─► WSS /ws/media-stream (Bidirectional WebSocket)
            ├── Twilio sends caller audio (20ms μ-law frames)
            ├── Backend STT (AssemblyAI) transcribes speech
            ├── Backend LLM (Gemini) generates response & executes tools
            ├── Backend TTS (ElevenLabs) streams synthesized μ-law frames
            └── Backend Pacer streams 20ms audio frames back to Twilio
```

---

## Step 1: Start the Backend Server

Ensure your FastAPI backend is running locally on port `8000`:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify it responds locally:
```powershell
curl http://localhost:8000/health/live
```
Expected output:
```json
{"status":"ok","service":"resort-voice-agent"}
```

---

## Step 2: Start Your ngrok Public Tunnel

In a separate terminal, expose port `8000` via your updated ngrok:

```powershell
& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000
```
*(Or simply `ngrok http 8000` if ngrok is in your system PATH).*

Copy the assigned **Forwarding HTTPS URL**, for example:
```
https://abcdef123456.ngrok-free.app
```

> [!NOTE]
> Keep this terminal open. If ngrok is stopped or restarted, the public forwarding URL will change (unless you have a reserved ngrok static domain).

---

## Step 3: Update `PUBLIC_BASE_URL` in `.env`

Open your `.env` file and set `PUBLIC_BASE_URL` to your ngrok HTTPS URL:

```env
PUBLIC_BASE_URL=https://abcdef123456.ngrok-free.app
```

Save `.env`.

---

## Step 4: Verify Health & Readiness

Check the readiness probe through your public tunnel:

```powershell
curl https://abcdef123456.ngrok-free.app/health/ready
```

Look for:
```json
{
  "status": "ready",
  "ready_for_real_calls": true,
  "public_url": {
    "is_https": true,
    "is_public": true
  },
  "missing_requirements": []
}
```

If `missing_requirements` lists any items, address them before dialing.

---

## Step 5: Configure the Twilio Phone Number

1. Log in to the [Twilio Console](https://console.twilio.com/).
2. Navigate to **Phone Numbers** -> **Manage** -> **Active Numbers**.
3. Click on your active Twilio phone number.
4. Scroll down to the **Voice Configuration** section:
   - Under **A CALL COMES IN**, select **Webhook**.
   - **URL**: Enter your webhook endpoint:
     ```
     https://abcdef123456.ngrok-free.app/telephony/incoming-call
     ```
   - **HTTP Method**: Select `HTTP POST`.
5. Click **Save configuration** at the bottom of the page.

---

## Step 6: Place a Real Test Call

1. Using your mobile phone, dial your Twilio phone number.
2. **Greeting Verification**: Within 1-2 seconds of connection, you should hear the assistant welcome greeting:
   *"Welcome to Azure Paradise Resort! How may I assist you with your stay today?"*
3. **Conversational Turn Verification**:
   - Ask: *"What room types do you offer?"*
   - Or ask: *"Can I check availability for next weekend?"*
   - Listen for the real-time spoken response synthesized by ElevenLabs.
4. **Barge-In / Interruption Verification**:
   - While the agent is speaking a long description, speak loudly: *"Excuse me, wait a second!"*
   - Verify that the agent immediately stops talking within ~200ms and listens to your new question.
5. Hang up when finished.

---

## Troubleshooting

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **"An application error has occurred. Goodbye."** | Webhook returned 500 or unreachable URL | Check uvicorn terminal logs. Ensure ngrok is running and URL matches Twilio webhook. |
| **Call connects, silence, then hangs up** | Media stream WebSocket failed to connect | Check `PUBLIC_BASE_URL` in `.env`. Ensure it starts with `https://` (which converts to `wss://`). |
| **HTTP 403 on `/telephony/incoming-call`** | Twilio signature mismatch | Ensure `TWILIO_AUTH_TOKEN` in `.env` matches the Twilio Console Auth Token. |
| **STT transcription not triggering** | AssemblyAI key or network issue | Check backend logs for `STT provider connection error`. |
