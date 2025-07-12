# HW Buddy Frontend - Backend Audio Integration

This document describes the frontend changes for the new backend audio streaming architecture.

## 🎯 What Changed

### Removed:
- `@google/genai` dependency and Gemini Live client integration
- Direct Gemini Live API calls from frontend
- Frontend audio processing for Gemini Live

### Added:
- `BackendAudioClient` for WebSocket communication with backend
- `BackendAudioSession` component replacing `GeminiLiveSession`
- Updated audio utilities for backend communication
- Real-time status indicators and error handling

## 🏗️ New Architecture

```
Frontend WebSocket ←→ Backend ADK Live Agent
     ↓                        ↓
Audio Capture            Audio Generation
Audio Playback           Image Analysis
UI Updates               Session Management
```

## 📁 New Files

### `src/app/utils/backendAudioClient.ts`
- WebSocket audio streaming client
- Handles bidirectional audio communication
- Event-driven architecture with callbacks

### `src/app/utils/backendAudio.ts`
- Audio encoding/decoding utilities
- PCM format conversion functions
- Audio quality detection and analysis

### `src/app/components/BackendAudioSession.tsx`
- Main session component for backend integration
- Real-time status updates and error handling
- MathJax display and processing status

## 🎵 Audio Flow

### Recording (Frontend → Backend):
1. Microphone → AudioContext (16kHz)
2. AudioWorkletNode → Float32Array
3. Float32Array → Int16Array → Base64
4. WebSocket → Backend ADK Live

### Playback (Backend → Frontend):
1. Backend ADK Live → WebSocket
2. Base64 → Int16Array → Float32Array
3. Float32Array → AudioBuffer (24kHz)
4. AudioBuffer → Speakers

## 🔌 WebSocket Protocol

### Messages to Backend:
```json
{
  "type": "audio",
  "data": "base64_encoded_pcm_audio"
}

{
  "type": "start_recording"
}

{
  "type": "stop_recording"
}
```

### Messages from Backend:
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
  "data": {"tool": "take_picture_and_analyze"}
}

{
  "type": "turn_complete"
}
```

## 🚀 Running the Frontend

### 1. Install Dependencies
```bash
cd web-app
npm install  # Note: @google/genai removed
```

### 2. Configure Environment
```bash
cp .env.example .env.local
# Edit .env.local if needed (defaults should work)
```

### 3. Start Development Server
```bash
npm run dev
```

### 4. Backend Requirements
Make sure the backend is running:
```bash
cd ../backend
./start_live_server.sh
```

## 🔧 Configuration

### Environment Variables
```bash
NEXT_PUBLIC_BACKEND_URL=ws://localhost:8000
NEXT_PUBLIC_BACKEND_HTTP_URL=http://localhost:8000
NEXT_PUBLIC_INPUT_SAMPLE_RATE=16000
NEXT_PUBLIC_OUTPUT_SAMPLE_RATE=24000
```

### Audio Settings
- **Input**: 16kHz PCM, mono channel
- **Output**: 24kHz PCM, mono channel
- **Buffer Size**: 512 samples (input), 1024 samples (output)
- **Format**: Base64 encoded Int16Array over WebSocket

## 🎮 User Experience

### Connection Status
- Green indicator: Connected to backend
- Red indicator: Disconnected or error
- Automatic reconnection attempts

### Recording Flow
1. Click start button
2. Browser requests microphone permission
3. Recording indicator shows audio levels
4. Click stop or speak naturally
5. Backend processes and responds with audio

### Error Handling
- Microphone permission errors
- WebSocket connection failures
- Backend communication errors
- Audio processing errors

## 🔍 Debugging

### Browser Console
```javascript
// Enable audio debugging
localStorage.setItem('debug_audio', 'true');

// Check WebSocket connection
console.log('WebSocket state:', audioClient.connected);

// Monitor audio levels
audioClient.onAudioLevel = (level) => console.log('Audio level:', level);
```

### Network Tab
- Monitor WebSocket messages in browser dev tools
- Check for connection drops or errors
- Verify audio data transmission

### Common Issues

1. **Microphone Permission Denied**
   - Check browser permissions
   - Try HTTPS or localhost
   - Reset site permissions

2. **Backend Connection Failed**
   - Verify backend is running on port 8000
   - Check CORS configuration
   - Ensure WebSocket support

3. **No Audio Playback**
   - Check browser audio permissions
   - Verify AudioContext state
   - Test with different browsers

## 🔄 Migration Guide

### For Developers
1. Remove all `@google/genai` imports
2. Replace `GeminiLiveSession` with `BackendAudioSession`
3. Update audio utility imports to use `backendAudio.ts`
4. Test end-to-end audio flow with backend

### Testing Checklist
- [ ] WebSocket connection establishes
- [ ] Audio recording captures microphone
- [ ] Audio data streams to backend
- [ ] Backend responses play through speakers
- [ ] MathJax content displays correctly
- [ ] Error states handled gracefully
- [ ] Session management works properly

## ⚡ Performance

### Optimizations
- Efficient audio buffering (minimal latency)
- Base64 encoding optimized for WebSocket
- Automatic audio quality detection
- Memory management for audio buffers

### Monitoring
- Audio level visualization
- Connection status indicators
- Processing time feedback
- Error rate tracking

The frontend is now fully integrated with the backend ADK Live agent, providing a seamless audio streaming experience for homework tutoring!