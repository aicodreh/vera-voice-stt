"""
Vera Voice STT Module
Standalone Deepgram speech-to-text service
Ready to integrate with OpenClaw for Option A
"""

import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

# Configuration
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

app = FastAPI(title="Vera Voice STT")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the test interface"""
    with open("index.html", "r") as f:
        return f.read()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "vera-voice-stt"}


@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio transcription
    
    Frontend sends: binary audio chunks (16kHz, 16-bit PCM)
    Backend sends: JSON with transcription results
    """
    await websocket.accept()
    print("Client connected")
    
    if not DEEPGRAM_API_KEY:
        await websocket.send_json({
            "error": "DEEPGRAM_API_KEY not configured"
        })
        await websocket.close()
        return
    
    try:
        # Initialize Deepgram client
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        
        # Create a live transcription connection
        dg_connection = deepgram.listen.live.v("1")
        
        # Track transcription results
        transcript_parts = []
        
        # Event handlers
        def on_message(self, result, **kwargs):
            """Handle transcription results"""
            transcript = result.channel.alternatives[0].transcript
            if transcript:
                is_final = result.is_final
                print(f"Transcript ({'final' if is_final else 'interim'}): {transcript}")
                
                # Send to client
                asyncio.run(websocket.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "is_final": is_final,
                    "confidence": result.channel.alternatives[0].confidence
                }))
                
                if is_final:
                    transcript_parts.append(transcript)
        
        def on_error(self, error, **kwargs):
            """Handle errors"""
            print(f"Deepgram error: {error}")
            asyncio.run(websocket.send_json({
                "type": "error",
                "message": str(error)
            }))
        
        def on_close(self, close, **kwargs):
            """Handle connection close"""
            print("Deepgram connection closed")
        
        # Register event handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        
        # Configure live transcription options
        options = LiveOptions(
            model="nova-2",           # Best accuracy model
            language="en-US",
            smart_format=True,        # Auto punctuation & formatting
            interim_results=True,     # Get results as user speaks
            utterance_end_ms=1000,    # Detect end of speech
            vad_events=True,          # Voice activity detection
            encoding="linear16",      # 16-bit PCM
            sample_rate=16000,        # 16kHz
            channels=1                # Mono
        )
        
        # Start the connection
        if not dg_connection.start(options):
            await websocket.send_json({
                "error": "Failed to connect to Deepgram"
            })
            await websocket.close()
                      return
await websocket.send_json({
            "type": "status",
            "message": "Connected to Deepgram, ready for audio"
        })
        
        # Receive audio chunks from client
        try:
            while True:
                # Receive binary audio data
                data = await websocket.receive_bytes()
                
                # Send to Deepgram
                dg_connection.send(data)
                
        except WebSocketDisconnect:
            print("Client disconnected")
        finally:
            # Close Deepgram connection
            dg_connection.finish()
            
            # Send final transcript
            if transcript_parts:
                full_transcript = " ".join(transcript_parts)
                try:
                    await websocket.send_json({
                        "type": "final_transcript",
                        "text": full_transcript
                    })
                except:
                    pass
            
            print("Deepgram connection finished")
    
    except Exception as e:
        print(f"Error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

