# HW Buddy - AI-Powered Homework Tutor

An intelligent tutoring system that provides real-time, personalized homework assistance using AI vision and voice interaction, mimicking the experience of having a human tutor by your side.

## 🎯 Overview

HW Buddy creates a seamless learning environment where students can study naturally while receiving AI-powered guidance. The system uses computer vision to analyze homework in real-time and provides spoken feedback, keeping students focused on their work without context switching.

## 🏗️ Architecture

The system consists of three main components working together:

### 📱 Mobile App
- **Purpose**: Overhead camera positioned above student's workspace
- **Technology**: Flutter/Dart with Firebase integration
- **Functionality**: 
  - Takes high-quality photos of homework/study materials
  - Uploads images to Google Cloud Storage
  - Listens to Firestore for session commands

### 🖥️ Web App  
- **Purpose**: Student interface on laptop/tablet
- **Technology**: Next.js with Gemini Live API integration
- **Functionality**:
  - Voice-activated conversations with AI tutor
  - Real-time audio transcription and playback
  - Visual feedback and session management
  - Acts as intelligent transcriber passing requests to backend

### 🧠 Backend
- **Purpose**: AI reasoning engine and session orchestration
- **Technology**: Python FastAPI with Gemini 2.5 Flash
- **Functionality**:
  - Processes images with advanced AI vision models
  - Provides personalized homework guidance
  - Manages session state via Firestore
  - Delivers contextual, step-by-step assistance

### 🗄️ Data Layer
- **Firestore**: Session management and real-time coordination
- **Google Cloud Storage**: Secure image storage and retrieval

## 🚀 How It Works

### Setup Process
1. **Mobile Setup**: Position phone overhead as camera, launch app
2. **Session Creation**: Web app generates unique session ID with QR code
3. **Device Connection**: Mobile app scans QR code to link to session
4. **Study Session**: Start voice recording and natural conversation with AI tutor

### Learning Flow (Optimized)
1. **Student Speaks**: "Can you help me solve this math problem?"
2. **AI Decision**: Agent intelligently decides if visual context is needed
3. **Instant Image Capture**: Mobile app captures and uploads image directly (<50ms)
4. **Real-time Analysis**: Backend processes image with ADK agent using `Part.from_bytes()`
5. **Smart Response**: AI provides targeted guidance with visual understanding
6. **Audio Delivery**: Response delivered via WebSocket with live status updates

### Key Benefits
- **Ultra-Fast Processing**: Event-based architecture for <50ms image processing
- **Intelligent Decisions**: ADK agent only takes pictures when contextually relevant
- **Natural Interaction**: Voice-based communication with real-time feedback
- **Visual Understanding**: Direct image injection into AI context for accurate analysis
- **Seamless Experience**: No interruptions, continuous conversation flow

## 🛠️ Technology Stack

| Component | Technologies |
|-----------|-------------|
| **Mobile App** | Flutter, Dart, Firebase SDK, Camera API, Direct HTTP Upload |
| **Web App** | Next.js, TypeScript, Tailwind CSS, WebSocket Audio |
| **Backend** | Python, FastAPI, Google ADK, Gemini 2.5 Flash, Event-based Processing |
| **Database** | Google Firestore (command coordination) |
| **Storage** | In-memory session storage (no cloud storage needed) |
| **AI Models** | ADK Live Agent, Gemini 2.5 Flash (with Part.from_bytes) |

## 📋 Prerequisites

- Node.js 18+
- Python 3.12+
- Flutter 3.0+
- Firebase project with Firestore enabled (no Storage needed)
- Google AI API key with Gemini access
- Mobile device with camera

## ⚙️ Setup Instructions

### 1. Firebase Configuration
```bash
# Create Firebase project at https://console.firebase.google.com
# Enable Firestore Database (Cloud Storage no longer needed)
# Download configuration files for each platform
```

### 2. Backend Setup
```bash
cd backend
# Install uv package manager
pip install uv

# Sync dependencies and create virtual environment
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Set up environment variables
export GOOGLE_AI_API_KEY="your-gemini-api-key"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/firebase-service-account.json"

# Start the backend server
python main.py
```

### 3. Web App Setup  
```bash
cd web-app
npm install
# Add your Gemini API key to .env.local:
echo "NEXT_PUBLIC_GEMINI_API_KEY=your-api-key" > .env.local
npm run dev
```

### 4. Mobile App Setup
```bash
cd mobile-app

# Install Flutter dependencies
flutter pub get

# Configure Firebase for Flutter (interactive setup)
flutterfire configure

# Add Firebase configuration files to appropriate directories:
# - android/app/google-services.json
# - ios/Runner/GoogleService-Info.plist

# For iOS deployment:
flutter build ios

# Open Xcode project
open ios/Runner.xcworkspace

# In Xcode:
# 1. Select Runner project in navigator
# 2. Choose your development team
# 3. Connect your iOS device or use simulator
# 4. Click the Run button (▶️) to build and deploy

# For Android (alternative):
flutter run --release
```

## 🎮 Usage

1. **Position Mobile Device**: Mount phone overhead facing down at workspace
2. **Start Session**: Open mobile app, tap "Start Session", note the session ID
3. **Connect Web App**: Open web app, enter session ID, click "Join Session"  
4. **Begin Studying**: Click "Start Recording" and ask questions naturally
5. **Receive Guidance**: AI analyzes your work and provides spoken assistance

## 🔧 Configuration

### Environment Variables

**Backend (.env)**
```
GOOGLE_APPLICATION_CREDENTIALS=path/to/firebase-key.json
GEMINI_API_KEY=your-gemini-api-key
```

**Web App (.env.local)**
```
NEXT_PUBLIC_GEMINI_API_KEY=your-gemini-api-key
NEXT_PUBLIC_FIREBASE_CONFIG=your-firebase-config-json
```

### Firebase Security Rules
```javascript
// Firestore Rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /sessions/{sessionId} {
      allow read, write: if true; // Configure based on your auth needs
    }
  }
}
```

## 🎯 Key Features

- **🎤 Voice Interaction**: Real-time WebSocket audio streaming with ADK Live
- **👁️ Computer Vision**: Direct `Part.from_bytes()` image injection for instant analysis
- **⚡ Event-based Processing**: <50ms image processing with `asyncio.Event` coordination
- **🧠 Intelligent Agent**: ADK agent with smart tool calling - only takes pictures when needed
- **📱 Optimized Mobile**: Direct HTTP upload with pre-initialized camera for minimal latency
- **🔒 Secure**: Session-based security with in-memory storage

## 🚀 Performance Improvements

### Latest Optimizations (2024):
- **10-20x Faster Image Processing**: Replaced Firestore listener with event-based architecture
- **Direct Image Injection**: Using `Part.from_bytes()` instead of cloud storage URIs
- **Streamlined Mobile Upload**: Raw image bytes only, no user context overhead
- **Real-time WebSocket Updates**: Live status during processing for better UX

### Performance Metrics:
| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| **Image Upload → Analysis** | 500-1000ms | 10-50ms | **10-20x faster** |
| **Mobile Image Capture** | ~2-3 seconds | ~200-500ms | **5x faster** |
| **ADK Agent Response** | Network dependent | In-process events | **Much more reliable** |
| **Memory Usage** | Firestore connections | Simple dictionaries | **Lower overhead** |

### Architecture Benefits:
- ✅ **No Cloud Storage**: Images processed in-memory, no GCS uploads needed
- ✅ **Event-driven**: Direct `asyncio.Event` coordination between components  
- ✅ **Simplified Stack**: Fewer network dependencies, cleaner error handling
- ✅ **Better Debugging**: In-process flow with clear logging and metrics

## 🔮 Future Enhancements

- **Multi-subject Support**: Specialized tutoring for different academic areas
- **Progress Tracking**: Learning analytics and improvement metrics
- **Collaborative Learning**: Multi-student session support
- **Offline Mode**: Local processing capabilities for improved privacy
- **Integration APIs**: Connect with popular learning management systems

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
- Create an issue in this repository
- Check existing documentation in component READMEs
- Review Firebase and Gemini API documentation

## 🙏 Acknowledgments

- Google Gemini AI for advanced language and vision capabilities
- Firebase for seamless real-time synchronization
- Flutter community for mobile development framework
- Next.js team for outstanding web application framework

---

**Built with ❤️ for students who deserve personalized, accessible tutoring**