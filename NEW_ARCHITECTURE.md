# HW Buddy - New WebSocket Architecture

This document describes the new WebSocket-based architecture that mimics the Livewire project structure.

## Architecture Overview

The new architecture consists of:

1. **WebSocket Backend** (`backend/websocket_server.py`) - Real-time server using Gemini Live API
2. **Web App** (`web-app/`) - WebSocket client with voice interaction
3. **Mobile App** (`mobile-app/`) - Dual connectivity (WebSocket + Firestore)

## Key Components

### Backend (`backend/`)

- `websocket_server.py` - Main WebSocket server
- `core/websocket_handler.py` - Client connection and message handling
- `core/gemini_client.py` - Gemini Live API integration
- `core/session.py` - Session state management
- `core/tool_handler.py` - Image capture tool execution
- `config/hw_config.py` - Configuration and system instructions

### Web App (`web-app/`)

- `WebSocketGeminiSession.tsx` - New WebSocket-based live session component
- Real-time audio streaming to/from backend
- Live voice interaction with AI tutor
- Image display when captured

### Mobile App (`mobile-app/`)

- `websocket_service.dart` - WebSocket client service
- Dual connectivity: WebSocket + Firestore (backward compatibility)
- Real-time image upload notification

## Setup Instructions

### 1. Environment Setup (One-time)

```bash
# Configure environment (root level - configures ALL components)
cp .env.example .env
# Edit .env with your API keys and configuration
```

### 2. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Start HTTP server (for image uploads)
python main.py

# In another terminal: Start WebSocket server (for live audio)
python websocket_server.py
```

### 3. Web App Setup

```bash
cd web-app

# Install dependencies
npm install

# Start development server (automatically uses root .env)
npm run dev
```

### 4. Mobile App Setup

```bash
cd mobile-app

# Install dependencies
flutter pub get

# The app will automatically try WebSocket connection
# Falls back to Firestore if WebSocket unavailable
# Uses Firebase config from root .env
flutter run
```

## How It Works

### 1. Session Initialization
- Web app generates session ID and connects to WebSocket server
- Mobile app scans QR code and connects to same session
- Both clients join the session via WebSocket (mobile also uses Firestore)

### 2. Voice Interaction
- User speaks into web app
- Audio streams in real-time to WebSocket server
- Server forwards to Gemini Live API
- AI responses stream back as audio + text

### 3. Image Capture
- AI decides when to call `capture_image` tool
- Backend triggers mobile camera via Firestore/WebSocket
- Mobile app takes photo, uploads to Firebase Storage
- Image URL sent back to backend
- Backend downloads image and sends to Gemini for analysis
- AI provides contextual response based on homework image

### 4. Real-time Communication
- All responses stream in real-time
- Audio plays immediately as generated
- Text appears progressively
- Image analysis integrated seamlessly

## Key Improvements

1. **Real-time Streaming**: Direct WebSocket connection eliminates polling delays
2. **Live Audio**: Gemini Live API provides natural voice interaction
3. **Tool Integration**: Image capture seamlessly integrated into conversation flow
4. **Scalable Architecture**: Clean separation of concerns, easy to extend
5. **Backward Compatibility**: Mobile app still works with Firestore fallback

## Centralized Configuration

All components use a **single `.env` file** in the root directory:

### Root .env file (configures everything)
```bash
# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_WEB_API_KEY=your-web-api-key

# API Keys
GOOGLE_API_KEY=your-gemini-api-key
GEMINI_API_KEY=your-gemini-api-key

# Server Configuration
BACKEND_PORT=8000
WEBSOCKET_PORT=8081

# Frontend URLs
NEXT_PUBLIC_WEBSOCKET_URL=ws://localhost:8081
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_GEMINI_API_KEY=your-gemini-api-key

# Firebase Service Account
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
```

**Benefits of centralized config:**
- ✅ One file to manage all environment variables
- ✅ No duplication between components
- ✅ Easier deployment and team setup
- ✅ Consistent configuration across all services

## Testing the Architecture

1. **One-time setup**: Copy `.env.example` to `.env` and configure
2. **Start backend servers**:
   ```bash
   cd backend
   python main.py           # Terminal 1: HTTP server
   python websocket_server.py  # Terminal 2: WebSocket server
   ```
3. **Start web app**: `cd web-app && npm run dev`
4. **Deploy mobile app**: `cd mobile-app && flutter run`
5. **Test flow**:
   - Create session in web app
   - Scan QR code with mobile app  
   - Start voice conversation
   - AI will automatically capture images when needed
   - Verify real-time audio/text responses

The new architecture provides a much more responsive and natural tutoring experience while maintaining the core functionality of the original system.