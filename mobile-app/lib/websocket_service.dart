import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

class WebSocketService {
  WebSocketChannel? _channel;
  StreamController<Map<String, dynamic>>? _messageController;
  String? _sessionId;
  bool _isConnected = false;
  
  // Default WebSocket URL - can be configured
  static const String defaultWsUrl = 'ws://localhost:8081';
  
  Stream<Map<String, dynamic>> get messageStream => 
      _messageController?.stream ?? const Stream.empty();
  
  bool get isConnected => _isConnected;
  
  Future<bool> connect(String sessionId, {String? wsUrl}) async {
    try {
      _sessionId = sessionId;
      _messageController = StreamController<Map<String, dynamic>>.broadcast();
      
      final uri = Uri.parse(wsUrl ?? defaultWsUrl);
      _channel = WebSocketChannel.connect(uri);
      
      // Listen for connection establishment
      await _channel!.ready;
      _isConnected = true;
      
      // Join session as mobile client
      _sendMessage({
        'type': 'join_session',
        'session_id': sessionId,
        'client_type': 'mobile'
      });
      
      // Listen to incoming messages
      _channel!.stream.listen(
        (data) {
          try {
            final message = json.decode(data);
            _messageController?.add(message);
          } catch (e) {
            print('Error parsing WebSocket message: $e');
          }
        },
        onDone: () {
          _isConnected = false;
          _messageController?.close();
        },
        onError: (error) {
          print('WebSocket error: $error');
          _isConnected = false;
          _messageController?.addError(error);
        },
      );
      
      return true;
    } catch (e) {
      print('Failed to connect to WebSocket: $e');
      _isConnected = false;
      return false;
    }
  }
  
  void _sendMessage(Map<String, dynamic> message) {
    if (_channel != null && _isConnected) {
      _channel!.sink.add(json.encode(message));
    }
  }
  
  void sendImageUpload(String imageUrl, String? imageGcsUrl) {
    _sendMessage({
      'type': 'image_upload',
      'image_url': imageUrl,
      'image_gcs_url': imageGcsUrl,
    });
  }
  
  void sendImageUploadNotification(String sessionId) {
    _sendMessage({
      'type': 'image_uploaded',
      'session_id': sessionId,
      'message': 'Image uploaded via HTTP',
    });
  }
  
  void disconnect() {
    _isConnected = false;
    _channel?.sink.close(status.goingAway);
    _messageController?.close();
    _channel = null;
    _messageController = null;
  }
}