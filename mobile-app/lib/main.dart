
import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';
import 'package:qr_code_scanner/qr_code_scanner.dart';

import 'firebase_options.dart';
import 'camera_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase only if it hasn't been initialized yet
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
  bool _isProcessingImage = false;

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
    _statusMessage = 'Listening for commands...';

    FirebaseFirestore.instance.collection('sessions').doc(_sessionId).set({
      'status': 'ready',
      'command': 'none',
      'last_image_url': '',
      'last_image_gcs_url': '',
    });

    _sessionSubscription = FirebaseFirestore.instance
        .collection('sessions')
        .doc(_sessionId)
        .snapshots()
        .listen((snapshot) {
      if (snapshot.exists) {
        final data = snapshot.data() as Map<String, dynamic>;
        if (data['command'] == 'take_picture') {
          takePictureAndUpload();
        }
      }
    });

    notifyListeners();
  }

  void startSession() {
    _sessionId = const Uuid().v4();
    _isSessionActive = true;
    _statusMessage = 'Listening for commands...';

    FirebaseFirestore.instance.collection('sessions').doc(_sessionId).set({
      'status': 'ready',
      'command': 'none',
      'last_image_url': '',
      'last_image_gcs_url': '',
    });

    _sessionSubscription = FirebaseFirestore.instance
        .collection('sessions')
        .doc(_sessionId)
        .snapshots()
        .listen((snapshot) {
      if (snapshot.exists) {
        final data = snapshot.data() as Map<String, dynamic>;
        if (data['command'] == 'take_picture') {
          takePictureAndUpload();
        }
      }
    });

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
    // Prevent multiple simultaneous image processing
    if (_isProcessingImage) {
      print('Already processing an image, skipping...');
      return;
    }
    
    _isProcessingImage = true;
    _statusMessage = 'Taking picture...';
    notifyListeners();

    try {
      // Use pre-initialized camera service for fast capture
      final image = await CameraService.takePicture();
      
      _statusMessage = 'Compressing image...';
      notifyListeners();
      
      // Compress image to reduce upload time and storage costs
      final compressedImage = await CameraService.compressImage(image.path);

      _statusMessage = 'Uploading image...';
      notifyListeners();

      final fileName = 'images/$_sessionId/${DateTime.now().toIso8601String()}.jpg';
      final storageRef = FirebaseStorage.instance.ref().child(fileName);
      await storageRef.putFile(compressedImage);
      final downloadURL = await storageRef.getDownloadURL();
      
      // Get the bucket name from Firebase Storage
      final bucket = storageRef.bucket;
      final gcsUrl = 'gs://$bucket/$fileName';

      _statusMessage = 'Processing...';
      notifyListeners();

      await FirebaseFirestore.instance
          .collection('sessions')
          .doc(_sessionId)
          .update({
        'last_image_url': downloadURL,
        'last_image_gcs_url': gcsUrl,
        'command': 'done',
      });

      _statusMessage = 'Listening for commands...';
    } catch (e) {
      _statusMessage = 'Error: Could not upload photo - $e';
      print('Error in takePictureAndUpload: $e');
    } finally {
      _isProcessingImage = false;
      notifyListeners();
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
