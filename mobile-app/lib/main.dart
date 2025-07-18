
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';
import 'package:qr_code_scanner/qr_code_scanner.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'firebase_options.dart';
import 'camera_service.dart';

// Backend configuration
//const String BACKEND_URL = 'https://660deffd8b4d.ngrok-free.app';
const String BACKEND_URL = 'https://660deffd8b4d.ngrok-free.app';
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase only if not already initialized
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  } catch (e) {
    if (e.toString().contains('duplicate-app')) {
      print('Firebase already initialized, continuing...');
    } else {
      print('Firebase initialization error: $e');
      rethrow;
    }
  }
  
  // Pre-initialize camera service for faster picture taking
  try {
    await CameraService.initialize();
  } catch (e) {
    print('Warning: Could not pre-initialize camera: $e');
  }
  
  runApp(
    ChangeNotifierProvider(
      create: (context) => SessionModel(),
      child: const TutorCamApp(),
    ),
  );
}

class SessionModel extends ChangeNotifier {
  String? _sessionId;
  bool _isSessionActive = false;
  String _statusMessage = 'Ready';
  StreamSubscription? _sessionSubscription;
  bool _isScanning = false;
  bool _isTakingPicture = false;  // Prevent multiple simultaneous captures

  String? get sessionId => _sessionId;
  bool get isSessionActive => _isSessionActive;
  String get statusMessage => _statusMessage;
  bool get isScanning => _isScanning;

  void startScanning() {
    _isScanning = true;
    _statusMessage = 'Scanning QR code...';
    notifyListeners();
  }

  void stopScanning() {
    _isScanning = false;
    _statusMessage = 'Ready';
    notifyListeners();
  }


  void startSessionWithId(String sessionId) {
    _sessionId = sessionId;
    _isSessionActive = true;
    _isScanning = false;
    _statusMessage = 'Connecting to AI system...';

    // Set up Firestore session document
    FirebaseFirestore.instance.collection('sessions').doc(_sessionId).set({
      'status': 'ready',
      'command': 'none',
      'last_image_url': '',
      'last_image_gcs_url': '',
    });

    // Listen for AI commands via Firestore
    _sessionSubscription = FirebaseFirestore.instance
        .collection('sessions')
        .doc(_sessionId)
        .snapshots()
        .listen((snapshot) {
      if (snapshot.exists) {
        final data = snapshot.data() as Map<String, dynamic>;
        if (data['command'] == 'take_picture') {
          print('🔥 AI requested photo via Firestore - taking picture...');
          if (!_isTakingPicture) {
            _statusMessage = 'AI requested photo - taking picture...';
            notifyListeners();
            takePictureAndUpload();
          } else {
            print('📸 Picture already in progress, skipping duplicate request');
          }
        }
      }
    });

    _statusMessage = 'Connected! Listening for AI commands...';
    notifyListeners();
  }

  void startSession() {
    _sessionId = const Uuid().v4();
    _isSessionActive = true;
    _statusMessage = 'Connecting to AI system...';

    // Set up Firestore session document
    FirebaseFirestore.instance.collection('sessions').doc(_sessionId).set({
      'status': 'ready',
      'command': 'none',
      'last_image_url': '',
      'last_image_gcs_url': '',
    });

    // Listen for AI commands via Firestore
    _sessionSubscription = FirebaseFirestore.instance
        .collection('sessions')
        .doc(_sessionId)
        .snapshots()
        .listen((snapshot) {
      if (snapshot.exists) {
        final data = snapshot.data() as Map<String, dynamic>;
        if (data['command'] == 'take_picture') {
          print('🔥 AI requested photo via Firestore - taking picture...');
          if (!_isTakingPicture) {
            _statusMessage = 'AI requested photo - taking picture...';
            notifyListeners();
            takePictureAndUpload();
          } else {
            print('📸 Picture already in progress, skipping duplicate request');
          }
        }
      }
    });

    _statusMessage = 'Connected! Listening for AI commands...';
    notifyListeners();
  }

  void stopSession() {
    _sessionSubscription?.cancel();
    _isSessionActive = false;
    _sessionId = null;
    _statusMessage = 'Ready';
    notifyListeners();
  }

  Future<void> takePictureAndUpload() async {
    if (_isTakingPicture) {
      print('📸 Picture capture already in progress, skipping...');
      return;
    }
    
    _isTakingPicture = true;
    _statusMessage = 'Taking picture...';
    notifyListeners();

    try {
      // Use pre-initialized camera service for fast capture
      final image = await CameraService.takePicture();
      
      _statusMessage = 'Compressing image...';
      notifyListeners();
      
      // Compress image to reduce upload time
      final compressedImage = await CameraService.compressImage(image.path);

      _statusMessage = 'Uploading to backend...';
      notifyListeners();

      // Direct HTTP upload to backend - MUCH FASTER!
      final uri = Uri.parse('$BACKEND_URL/sessions/$_sessionId/upload_image');
      final request = http.MultipartRequest('POST', uri);
      
      // Add the image file with explicit content type
      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          compressedImage.path,
          filename: '${DateTime.now().millisecondsSinceEpoch}.jpg',
          contentType: MediaType('image', 'jpeg'),
        ),
      );
      
      // Mobile app only sends raw image data - no user context needed

      _statusMessage = 'Analyzing...';
      notifyListeners();

      // Send request and get response
      final response = await request.send();
      
      if (response.statusCode == 200) {
        _statusMessage = 'Image processed successfully!';
        
        // Parse response to get analysis results
        final responseBody = await response.stream.bytesToString();
        final jsonResponse = Map<String, dynamic>.from(
          await parseJsonResponse(responseBody)
        );
        
        print('Backend response: $jsonResponse');
        
        // IMPORTANT: Reset both command and status so we can receive new commands
        if (_sessionId != null) {
          await FirebaseFirestore.instance
              .collection('sessions')
              .doc(_sessionId)
              .update({
                'command': 'none',
                'status': 'ready'
              });
          print('📸 Reset command to none and status to ready after successful upload');
        }
        
        // Status will update to show analysis is complete
        _statusMessage = 'Ready for next question!';
      } else {
        throw Exception('Upload failed with status: ${response.statusCode}');
      }

    } catch (e) {
      _statusMessage = 'Error: Could not upload photo - $e';
      print('Error in takePictureAndUpload: $e');
    } finally {
      _isTakingPicture = false;  // Reset flag
      notifyListeners();
    }
  }
  
  // Helper function to parse JSON response
  Future<Map<String, dynamic>> parseJsonResponse(String responseBody) async {
    try {
      return json.decode(responseBody);
    } catch (e) {
      print('Error parsing response: $e');
      return {'success': false, 'error': 'Invalid response format'};
    }
  }
}

class QRScannerWidget extends StatefulWidget {
  final Function(String) onQRCodeScanned;

  const QRScannerWidget({Key? key, required this.onQRCodeScanned}) : super(key: key);

  @override
  State<QRScannerWidget> createState() => _QRScannerWidgetState();
}

class _QRScannerWidgetState extends State<QRScannerWidget> {
  final GlobalKey qrKey = GlobalKey(debugLabel: 'QR');
  QRViewController? controller;

  @override
  void reassemble() {
    super.reassemble();
    if (Platform.isAndroid) {
      controller!.pauseCamera();
    } else if (Platform.isIOS) {
      controller!.resumeCamera();
    }
  }

  @override
  Widget build(BuildContext context) {
    return QRView(
      key: qrKey,
      onQRViewCreated: _onQRViewCreated,
      overlay: QrScannerOverlayShape(
        borderColor: Colors.red,
        borderRadius: 10,
        borderLength: 30,
        borderWidth: 10,
        cutOutSize: 300,
      ),
    );
  }

  void _onQRViewCreated(QRViewController controller) {
    this.controller = controller;
    controller.scannedDataStream.listen((scanData) {
      if (scanData.code != null) {
        widget.onQRCodeScanned(scanData.code!);
      }
    });
  }

  @override
  void dispose() {
    controller?.dispose();
    super.dispose();
  }
}

class TutorCamApp extends StatelessWidget {
  const TutorCamApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(
          title: const Text('Tutor Cam'),
        ),
        body: Consumer<SessionModel>(
          builder: (context, session, child) {
            if (session.isScanning) {
              return Stack(
                children: [
                  QRScannerWidget(
                    onQRCodeScanned: (sessionId) {
                      session.startSessionWithId(sessionId);
                    },
                  ),
                  Positioned(
                    top: 20,
                    left: 20,
                    right: 20,
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.7),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Scan QR code from web app to connect',
                        style: const TextStyle(color: Colors.white),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                  Positioned(
                    bottom: 100,
                    left: 20,
                    right: 20,
                    child: ElevatedButton(
                      onPressed: () => session.stopScanning(),
                      child: const Text('Cancel'),
                    ),
                  ),
                ],
              );
            }

            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (session.isSessionActive)
                    Text('Session ID: ${session.sessionId}'),
                  Text(session.statusMessage),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: () {
                      if (session.isSessionActive) {
                        session.stopSession();
                      } else {
                        session.startScanning();
                      }
                    },
                    child: Text(
                      session.isSessionActive ? 'Stop Session' : 'Scan QR Code',
                    ),
                  ),
                  if (!session.isSessionActive) ...[
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: () => session.startSession(),
                      child: const Text('Start without QR code'),
                    ),
                  ],
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
