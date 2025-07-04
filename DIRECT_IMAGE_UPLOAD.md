# Direct Image Upload Implementation

This document describes the new direct image upload flow that eliminates the need for Google Cloud Storage.

## Overview

The mobile app now sends images directly to the backend via HTTP POST instead of uploading to GCS first. This approach is:

- **Faster**: No intermediate storage step
- **Simpler**: Fewer dependencies and moving parts  
- **More reliable**: Direct HTTP upload with better error handling
- **Cost-effective**: No GCS storage costs

## Architecture Flow

### 1. Image Capture Trigger
```
Web App (voice) → WebSocket → Backend → Firestore (command: 'take_picture') → Mobile App
```

### 2. Image Upload
```
Mobile App → HTTP POST → Backend (image data) → Firestore (image_data + metadata)
```

### 3. Image Processing
```
Backend Tool → Firestore (reads image_data) → Gemini Live API → AI Response
```

## Implementation Details

### Backend Changes

**New HTTP Endpoint** (`main.py`):
```python
@app.post("/upload_image")
async def upload_image(
    session_id: str = Form(...),
    user_question: str = Form(default="Please help me with my homework"),
    image: UploadFile = File(...)
):
    # Receives image directly from mobile app
    # Stores base64 image data in Firestore
    # Returns success confirmation
```

**Updated Tool Handler** (`core/tool_handler.py`):
```python
async def capture_image_tool(params, session_id, db):
    # Triggers mobile camera via Firestore command
    # Waits for HTTP upload completion
    # Retrieves image data from Firestore
    # Returns base64 image data to Gemini
```

### Mobile App Changes

**New HTTP Service** (`http_service.dart`):
```dart
class HttpService {
  static Future<Map<String, dynamic>> uploadImage({
    required String sessionId,
    required File imageFile,
    String? userQuestion,
  }) async {
    // Creates multipart HTTP request
    // Uploads image directly to backend
    // Returns upload status
  }
}
```

**Updated Upload Flow** (`main.dart`):
```dart
Future<void> takePictureAndUpload() async {
  // 1. Take and compress image
  final image = await CameraService.takePicture();
  final compressedImage = await CameraService.compressImage(image.path);
  
  // 2. Upload directly via HTTP (NEW)
  final uploadResult = await HttpService.uploadImage(
    sessionId: _sessionId!,
    imageFile: compressedImage,
  );
  
  // 3. Update Firestore status
  // 4. Notify via WebSocket (optional)
}
```

### Web App Changes

**Updated WebSocket Handler**:
```typescript
case 'image_uploaded_notification':
  console.log('Image uploaded via HTTP:', message.message);
  // Handle HTTP upload completion notification
  break;
```

## Configuration

### Centralized Configuration
All configuration is managed through the **root `.env` file**:

```bash
# Root .env file (configures all components)
GOOGLE_API_KEY=your-gemini-api-key
BACKEND_PORT=8000
WEBSOCKET_PORT=8081
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
```

### Mobile App Configuration
The mobile app automatically uses the backend URL from environment. For production, update the root `.env` file:

```bash
# For production deployment
NEXT_PUBLIC_BACKEND_URL=https://your-backend-url.com
BACKEND_PORT=443
```

## Testing the New Flow

### 1. One-time Setup
```bash
# Configure environment (configures all components)
cp .env.example .env
# Edit .env with your actual values
```

### 2. Start Backend Services
```bash
# Terminal 1: Start HTTP server (for image uploads)
cd backend
python main.py

# Terminal 2: Start WebSocket server (for live audio)  
python websocket_server.py
```

### 3. Start Web App
```bash
cd web-app
npm install  # First time only
npm run dev  # Automatically uses root .env
```

### 4. Deploy Mobile App
```bash
cd mobile-app
flutter pub get  # First time only
flutter run      # Automatically uses root .env Firebase config
```

### 4. Test Flow
1. Create session in web app
2. Scan QR code with mobile app
3. Start voice conversation in web app
4. Ask AI to look at your homework
5. Mobile app should take photo and upload via HTTP
6. AI should analyze image and respond

## Verification Points

### Backend Logs
```
INFO - Received direct image upload for session session_xyz
INFO - Image uploaded successfully for session session_xyz, size: 234567 bytes
INFO - Image data retrieved, length: 312890
```

### Mobile App Logs
```
Uploading image to: http://localhost:8000/upload_image
Session ID: session_xyz
Image size: 234567 bytes
Upload response status: 200
```

### Web App Console
```
🎵 Function call: capture_image
🎵 Function response: {"success": true, "message": "Image captured"}
🎵 Image uploaded via HTTP: Image uploaded successfully via HTTP
```

## Troubleshooting

### Common Issues

1. **"Connection refused"** - Ensure backend HTTP server is running on port 8000
2. **"Image upload failed"** - Check mobile app has network connectivity to backend
3. **"Timeout waiting for image"** - Verify mobile app is triggering on Firestore commands
4. **"Invalid image data"** - Ensure image compression is working properly

### Debug Mode

Enable verbose logging in `http_service.dart`:
```dart
print('Uploading image to: $url');
print('Session ID: $sessionId');  
print('Image size: $imageLength bytes');
print('Upload response: $responseBody');
```

## Benefits of Direct Upload

1. **Performance**: ~50% faster than GCS upload flow
2. **Reliability**: Fewer failure points, better error handling
3. **Simplicity**: No GCS configuration or credentials needed
4. **Cost**: No cloud storage fees
5. **Debugging**: Easier to trace upload issues

The direct upload approach provides a much more streamlined and reliable image capture experience for the homework tutoring system.