import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';

class CameraService {
  static CameraController? _controller;
  static bool _isInitialized = false;
  static bool _isInitializing = false;
  static bool _isTakingPicture = false;

  /// Pre-initialize camera at app startup for faster picture taking
  static Future<void> initialize() async {
    if (_isInitialized || _isInitializing) return;
    
    _isInitializing = true;
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw Exception('No cameras available on device');
      }

      _controller = CameraController(
        cameras.first,
        ResolutionPreset.low, // Reduced from medium for faster processing
        enableAudio: false,   // Not needed for homework capture
      );

      await _controller!.initialize();
      _isInitialized = true;
    } catch (e) {
      _isInitialized = false;
      rethrow;
    } finally {
      _isInitializing = false;
    }
  }

  /// Fast picture capture using pre-initialized controller
  static Future<XFile> takePicture() async {
    // Prevent multiple simultaneous picture captures
    if (_isTakingPicture) {
      throw Exception('Camera is already taking a picture. Please wait.');
    }
    
    _isTakingPicture = true;
    
    try {
      if (!_isInitialized) {
        await initialize();
      }
      
      if (_controller == null || !_controller!.value.isInitialized) {
        throw Exception('Camera not properly initialized');
      }

      return await _controller!.takePicture();
    } finally {
      _isTakingPicture = false;
    }
  }

  /// Compress image to reduce upload time and storage costs
  static Future<File> compressImage(String imagePath) async {
    final compressedFile = await FlutterImageCompress.compressAndGetFile(
      imagePath,
      imagePath.replaceAll('.jpg', '_compressed.jpg'),
      quality: 70,        // Good quality while reducing file size
      minWidth: 1024,     // Sufficient resolution for homework text
      minHeight: 768,     // Sufficient resolution for homework text
      rotate: 0,          // Keep original orientation
    );

    if (compressedFile == null) {
      throw Exception('Failed to compress image');
    }

    return File(compressedFile.path);
  }

  /// Clean up camera resources
  static Future<void> dispose() async {
    if (_controller != null) {
      await _controller!.dispose();
      _controller = null;
      _isInitialized = false;
    }
  }

  /// Check if camera is ready for use
  static bool get isReady => _isInitialized && _controller != null;

  /// Get camera controller for advanced usage if needed
  static CameraController? get controller => _controller;
}