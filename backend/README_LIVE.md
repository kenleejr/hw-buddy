# HW Buddy Live Backend

This is the updated backend implementation using Google's ADK Live API for real-time audio streaming and homework tutoring.

## 🎯 New Architecture

### Key Changes from Original:
- **ADK Live Agent**: Replaced standard ADK agent with Live API integration
- **Audio Streaming**: Direct WebSocket audio communication (no Gemini Live on frontend)
- **Direct Image Upload**: Mobile app uploads images directly to backend
- **Real-time Processing**: Bidirectional audio streaming with low latency

### Components:

#### 1. `hw_live_agent.py`
- ADK Live agent for homework tutoring
- Manages audio streaming and image analysis
- Session state management

#### 2. `audio_websocket_server.py` 
- WebSocket manager for audio streaming
- Handles bidirectional audio communication
- Event processing from ADK agent

#### 3. `image_upload_handler.py`
- Direct image upload processing
- Image validation and analysis
- Integration with ADK agent

#### 4. `main_live.py`
- Updated FastAPI server
- WebSocket and HTTP endpoints
- Session management

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd backend
uv sync
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Google Cloud and API credentials
```

### 3. Start the Server
```bash
./start_live_server.sh
```

Or manually:
```bash
python main_live.py
```

## 📡 API Endpoints

### Session Management
```http
POST /sessions
GET /sessions/{session_id}/status
DELETE /sessions/{session_id}
```

### Audio Streaming
```http
WebSocket: ws://localhost:8000/ws/audio/{session_id}
```

### Image Upload
```http
POST /sessions/{session_id}/upload_image
GET /sessions/{session_id}/image_status
```

### Legacy Compatibility
```http
POST /take_picture  # For gradual migration
```

## 🔧 WebSocket Audio Protocol

### Client → Server Messages:
```json
{
  "type": "audio",
  "data": "base64_encoded_pcm_audio"
}

{
  "type": "start_recording",
  "data": {}
}

{
  "type": "stop_recording", 
  "data": {}
}
```

### Server → Client Messages:
```json
{
  "type": "audio",
  "data": "base64_encoded_pcm_audio"
}

{
  "type": "agent_ready",
  "data": {"message": "Ready to help!"}
}

{
  "type": "tool_call",
  "data": {"tool": "take_picture_and_analyze", "message": "Taking picture..."}
}

{
  "type": "turn_complete",
  "data": {"message": "Ready for next question!"}
}
```

## 🎵 Audio Configuration

- **Input**: 16kHz PCM from frontend
- **Output**: 24kHz PCM to frontend  
- **Format**: Base64 encoded binary data over WebSocket
- **Voice**: Aoede (configurable in .env)

## 📱 Mobile App Integration

The mobile app should now upload images directly:

```http
POST /sessions/{session_id}/upload_image
Content-Type: multipart/form-data

file: <image_file>
user_ask: "What's the next step in this problem?"
```

## 🔍 Debugging

### Debug Endpoints:
```http
GET /debug/sessions  # List all active sessions
GET /health         # Health check
```

### Logs:
- Session creation/destruction
- Audio streaming events
- Image upload and processing
- ADK agent interactions

## 🔄 Migration from Original Backend

### What Changed:
1. **Audio**: Moved from frontend Gemini Live to backend ADK Live
2. **Images**: Direct upload instead of Firebase Storage
3. **Communication**: WebSocket for audio + HTTP for images
4. **Session State**: Managed in backend memory

### What Stayed:
1. **Core Logic**: Homework analysis and tutoring prompts
2. **API Structure**: Similar endpoint patterns for compatibility
3. **Session Management**: Same session ID concepts

## ⚙️ Configuration

### Required Environment Variables:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
# OR
GOOGLE_AI_API_KEY=your-gemini-api-key
```

### Optional Configuration:
```bash
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
VOICE_NAME=Aoede
RECEIVE_SAMPLE_RATE=24000
SEND_SAMPLE_RATE=16000
```

## 🎯 Next Steps

1. **Frontend Update**: Remove Gemini Live, add WebSocket audio streaming
2. **Mobile Update**: Change to direct HTTP image upload
3. **Testing**: End-to-end audio and image flow
4. **Performance**: Optimize audio buffering and latency

## 🔧 Development

### Running in Development:
```bash
uvicorn main_live:app --reload --host 0.0.0.0 --port 8000
```

### Testing Audio Streaming:
Use the WebSocket test client or browser developer tools to test audio message flow.

### Testing Image Upload:
```bash
curl -X POST \
  "http://localhost:8000/sessions/test_session/upload_image" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_image.jpg" \
  -F "user_ask=Help me solve this problem"
```