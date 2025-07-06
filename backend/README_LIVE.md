# HW Buddy Live Backend

This is the updated backend implementation using Google's ADK Live API for real-time audio streaming and homework tutoring with robust connection management and duplicate prevention.

## 🎯 New Architecture

### Key Changes from Original:
- **ADK Live Agent**: Replaced standard ADK agent with Live API integration
- **Audio Streaming**: Direct WebSocket audio communication (no Gemini Live on frontend)
- **Direct Image Upload**: Mobile app uploads images directly to backend
- **Real-time Processing**: Bidirectional audio streaming with low latency
- **Connection Management**: Prevents duplicate WebSocket connections per session
- **Robust Error Handling**: Graceful rejection of duplicate connections

### Components:

#### 1. `hw_live_agent.py`
- ADK Live agent for homework tutoring
- Manages audio streaming and image analysis
- Session state management

#### 2. `audio_websocket_server.py` 
- WebSocket manager for audio streaming
- Handles bidirectional audio communication
- Event processing from ADK agent
- **Connection Deduplication**: Rejects duplicate connections per session
- **Session Isolation**: Each session maintains single active connection

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

### Connection Management:
- **One Connection Per Session**: Each session ID can have only one active WebSocket connection
- **Duplicate Rejection**: New connections to existing sessions are rejected with code `1008`
- **Graceful Cleanup**: Proper resource cleanup on disconnection

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

{
  "type": "recording_started",
  "data": {"message": "Recording started"}
}

{
  "type": "recording_stopped", 
  "data": {"message": "Recording stopped"}
}

{
  "type": "interrupted",
  "data": {"message": "Response interrupted"}
}

{
  "type": "error",
  "data": {"message": "Error occurred"}
}
```

### Connection Rejection:
When a duplicate connection is attempted:
```json
WebSocket Close Code: 1008
Reason: "Session already has active connection"
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
- **Connection Management**: Duplicate connection attempts and rejections
- **WebSocket Events**: Connection/disconnection events with session tracking

### Common Log Messages:
```
INFO - Audio WebSocket connected for session session_abc123
WARNING - Rejecting duplicate WebSocket connection for session session_abc123  
INFO - Audio WebSocket disconnected for session session_abc123
INFO - Cancelled agent session task for session_abc123
```

### Troubleshooting:
1. **Multiple Connections**: If you see duplicate rejection logs, check frontend for React StrictMode or double useEffect calls
2. **Connection Failures**: Ensure backend is running and WebSocket endpoint is accessible
3. **Audio Issues**: Check sample rates (16kHz input, 24kHz output) and PCM format
4. **Session Issues**: Verify session ID format and that sessions are properly created before WebSocket connection

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

## 🎯 Production Considerations

### Connection Management:
1. **Session Cleanup**: Implement session timeout for abandoned connections
2. **Load Balancing**: Consider session affinity if using multiple backend instances
3. **Rate Limiting**: Add rate limiting for connection attempts per IP/session

### Performance:
1. **Audio Buffering**: Optimize audio queue management for lower latency
2. **Memory Management**: Monitor session memory usage and cleanup
3. **Concurrent Sessions**: Test with multiple simultaneous audio sessions

### Security:
1. **Session Validation**: Implement proper session ID validation and expiration
2. **Audio Validation**: Validate audio data format and size limits
3. **Connection Limits**: Implement per-IP connection limits

### Monitoring:
1. **Metrics**: Track active sessions, connection attempts, rejections
2. **Health Checks**: Monitor WebSocket connection health
3. **Error Tracking**: Log and track connection errors and failures

## 🖥️ Frontend Integration

### WebSocket Audio Client:
The frontend uses `BackendAudioClient` class for audio streaming:

```typescript
const audioClient = new BackendAudioClient({
  inputSampleRate: 16000,
  outputSampleRate: 24000,
  inputBufferSize: 512,
  outputBufferSize: 1024,
});

// Connection with duplicate prevention
await audioClient.connect(sessionId, 'ws://localhost:8000');

// Event handlers
audioClient.onMessage = (message) => {
  switch (message.type) {
    case 'agent_ready':
      console.log('Agent ready!');
      break;
    case 'audio':
      // Handle audio playback
      break;
    case 'turn_complete':
      console.log('Turn complete');
      break;
  }
};
```

### Connection Management:
- **Duplicate Prevention**: Frontend checks for existing connections before creating new ones
- **React StrictMode**: Disabled in development to prevent double useEffect execution
- **Error Handling**: Graceful handling of connection rejections

### Key Frontend Files:
- `backendAudioClient.ts`: WebSocket audio client with connection management
- `BackendAudioSession.tsx`: React component managing audio session
- `backendAudio.ts`: Audio processing utilities

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

### Testing Connection Management:
1. Open browser dev tools
2. Connect to a session via WebSocket
3. Try connecting again with same session ID
4. Verify second connection is rejected with code 1008