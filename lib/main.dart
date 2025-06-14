
import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';

import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
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

  String? get sessionId => _sessionId;
  bool get isSessionActive => _isSessionActive;
  String get statusMessage => _statusMessage;

  void startSession() {
    _sessionId = const Uuid().v4();
    _isSessionActive = true;
    _statusMessage = 'Listening for commands...';

    FirebaseFirestore.instance.collection('sessions').doc(_sessionId).set({
      'status': 'ready',
      'command': 'none',
      'last_image_url': '',
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
    _statusMessage = 'Taking picture...';
    notifyListeners();

    try {
      final cameras = await availableCameras();
      final firstCamera = cameras.first;

      final controller = CameraController(
        firstCamera,
        ResolutionPreset.medium,
      );

      await controller.initialize();
      final image = await controller.takePicture();

      final storageRef = FirebaseStorage.instance
          .ref()
          .child('images/$_sessionId/${DateTime.now().toIso8601String()}.jpg');
      await storageRef.putFile(File(image.path));
      final downloadURL = await storageRef.getDownloadURL();

      await FirebaseFirestore.instance
          .collection('sessions')
          .doc(_sessionId)
          .update({
        'last_image_url': downloadURL,
        'command': 'done',
      });

      _statusMessage = 'Listening for commands...';
    } catch (e) {
      _statusMessage = 'Error: Could not upload photo';
    } finally {
      notifyListeners();
    }
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
        body: Center(
          child: Consumer<SessionModel>(
            builder: (context, session, child) {
              return Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (session.isSessionActive)
                    Text('Session ID: ${session.sessionId}'),
                  Text(session.statusMessage),
                  ElevatedButton(
                    onPressed: () {
                      if (session.isSessionActive) {
                        session.stopSession();
                      } else {
                        session.startSession();
                      }
                    },
                    child: Text(
                      session.isSessionActive ? 'Stop Session' : 'Start Session',
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
