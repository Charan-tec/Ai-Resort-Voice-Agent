import asyncio
import json
import websockets

async def test_live_ws():
    uri = 'ws://localhost:8000/ws/browser-voice'
    async with websockets.connect(uri) as ws:
        # 1. Connected
        msg = await ws.recv()
        print('RECV:', msg, flush=True)
        
        # 2. Start
        await ws.send(json.dumps({'event': 'start', 'session_id': 'browser_audit_1'}))
        msg = await ws.recv()
        print('RECV session_state:', msg, flush=True)
        
        # Drain initial greeting audio/marks/transcripts
        greeting_text = ''
        while True:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(m)
                if data.get('event') == 'transcript' and data.get('role') == 'assistant':
                    greeting_text = data.get('content')
                if data.get('event') == 'mark' and 'browser_turn_end' in data.get('mark', {}).get('name', ''):
                    break
            except asyncio.TimeoutError:
                break
        print('Greeting heard:', greeting_text, flush=True)
        
        turns = [
            "I need a room for two guests for november 22 and 25",
            "check-in date is november 22 on checkout date is november 25th",
            "which one is the cheapest",
            "book that one"
        ]
        
        for idx, t in enumerate(turns, 1):
            print(f'\n--- SENDING TURN {idx}: "{t}" ---', flush=True)
            await ws.send(json.dumps({
                'event': 'transcript',
                'text': t,
                'is_final': True,
                'turn_id': f'user_{idx}'
            }))
            
            # Collect response
            asst_text = ''
            all_events = []
            while True:
                try:
                    m = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(m)
                    evt = data.get('event')
                    all_events.append(evt)
                    if evt == 'transcript' and data.get('role') == 'assistant':
                        asst_text = data.get('content')
                    elif evt == 'mark' and 'browser_turn_end' in data.get('mark', {}).get('name', ''):
                        break
                except asyncio.TimeoutError:
                    print('Timed out waiting for response', flush=True)
                    break
            print(f'AGENT TURN {idx} RESPONSE: "{asst_text}"', flush=True)
            print(f'Events received: {all_events[:10]}... (total {len(all_events)})', flush=True)
            await asyncio.sleep(0.5)

if __name__ == '__main__':
    asyncio.run(test_live_ws())
