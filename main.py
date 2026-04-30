"""
Vera Voice STT Module (Async Version)
Standalone Deepgram speech-to-text service
Ready to integrate with OpenClaw for Option A
"""

import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

app = FastAPI(title="Vera Voice STT")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r") as f:
        return f.read()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vera-voice-stt"}


@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")
    
    if not DEEPGRAM_API_KEY:
        await websocket.send_json({"error": "DEEPGRAM_API_KEY not configured"})
        await websocket.close()
        return
    
    transcript_parts = []
    dg_connection = None
    
    try:
        config = DeepgramClientOptions(options={"keepalive": "true"})
        deepgram = DeepgramClient(DEEPGRAM_API_KEY, config)
        dg_connection = deepgram.listen.asynclive.v("1")
        
        async def on_message(self, result, **kwargs):
            try:
                transcript = result.channel.alternatives[0].transcript
                if transcript:
                    is_final = result.is_final
                    print(f"Transcript ({'final' if is_final else 'interim'}): {transcript}")
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript,
                        "is_final": is_final,
                        "confidence": result.channel.alternatives[0].confidence
                    })
                    if is_final:
                        transcript_parts.append(transcript)
            except Exception as e:
                print(f"Error in on_message: {e}")
        
        async def on_error(self, error, **kwargs):
            print(f"Deepgram error: {error}")
            try:
                await websocket.send_json({"type": "error", "message": str(error)})
            except:
                pass
        
        async def on_close(self, close, **kwargs):
            print("Deepgram connection closed")
        
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        
        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            interim_results=True,
            utterance_end_ms=1000,
            encoding="linear16",
            sample_rate=16000,
            channels=1
        )
        
        if await dg_connection.start(options) is False:
            await websocket.send_json({"error": "Failed to connect to Deepgram"})
            await websocket.close()
            return
        
        await websocket.send_json({"type": "status", "message": "Connected to Deepgram, ready for audio"})
        
        while True:
            try:
                data = await websocket.receive_bytes()
                await dg_connection.send(data)
            except WebSocketDisconnect:
                print("Client disconnected")
                break
            except Exception as e:
                print(f"Error receiving audio: {e}")
                break
    
    except Exception as e:
        print(f"Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    
    finally:
        if dg_connection:
            try:
                await dg_connection.finish()
            except:
                pass
        
        if transcript_parts:
            full_transcript = " ".join(transcript_parts)
            try:
                await websocket.send_json({"type": "final_transcript", "text": full_transcript})
            except:
                pass
        
        print("Connection finished")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
