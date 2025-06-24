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
2. **Session Creation**: Click "Start Session" to generate unique session key
3. **Web Connection**: Enter session key in web app to link devices
4. **Study Begin**: Click record and start natural conversation with AI tutor

### Learning Flow
1. **Student Speaks**: "Can you help me solve this math problem?"
2. **Image Capture**: AI automatically triggers phone to photograph workspace
3. **Visual Analysis**: Backend processes image with user's specific question
4. **Smart Response**: AI provides targeted guidance and next steps
5. **Audio Delivery**: Response is spoken back to student naturally

### Key Benefits
- **Context Preservation**: Students stay focused on their work
- **Natural Interaction**: Voice-based communication feels human-like  
- **Visual Understanding**: AI sees and analyzes actual homework content
- **Personalized Guidance**: Responses tailored to specific questions and work shown
- **Continuous Flow**: Seamless feedback loop encourages active learning

## 🛠️ Technology Stack

| Component | Technologies |
|-----------|-------------|
| **Mobile App** | Flutter, Dart, Firebase SDK, Camera API, Cloud Storage |
| **Web App** | Next.js, TypeScript, Tailwind CSS, Gemini Live API |
| **Backend** | Python, FastAPI, Gemini 2.5 Flash, Firebase Admin SDK |
| **Database** | Google Firestore (real-time sync) |
| **Storage** | Google Cloud Storage (image hosting) |
| **AI Models** | Gemini Live (frontend), Gemini 2.5 Flash (backend reasoning) |

## 📋 Prerequisites

- Node.js 18+
- Python 3.9+
- Flutter 3.0+
- Firebase project with Firestore and Storage enabled
- Google AI API key with Gemini access
- Mobile device with camera

## ⚙️ Setup Instructions

### 1. Firebase Configuration
```bash
# Create Firebase project at https://console.firebase.google.com
# Enable Firestore Database and Cloud Storage
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

# Set up Firebase credentials
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# Start the backend server
uvicorn main:app --reload --port 8000
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

- **🎤 Voice Interaction**: Natural speech recognition and synthesis
- **👁️ Computer Vision**: Advanced homework analysis and understanding  
- **⚡ Real-time Sync**: Instant coordination between all components
- **🧠 Contextual AI**: Responses tailored to specific questions and visual content
- **📱 Cross-platform**: Works on iOS, Android, and web browsers
- **🔒 Secure**: Firebase security with private session management

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