# Vera Voice STT

Standalone Deepgram speech-to-text module for Vera Voice Option A integration.

## Setup

1. Deploy to Railway
2. Set environment variable: `DEEPGRAM_API_KEY`
3. Open the deployed URL and test

## API

- `GET /` — Test interface with mic button
- `GET /health` — Health check
- `WS /listen` — WebSocket for audio streaming

## Integration

When ready to connect to OpenClaw:
1. Receive final transcript from this module
2. POST to OpenClaw `/v1/chat/completions`
3. Return response with TTS
