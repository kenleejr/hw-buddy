import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

class HttpService {
  // Default backend URL - can be configured
  static const String defaultBackendUrl = 'http://localhost:8000';
  
  static Future<Map<String, dynamic>> uploadImage({
    required String sessionId,
    required File imageFile,
    String? userQuestion,
    String? backendUrl,
  }) async {
    try {
      final url = Uri.parse('${backendUrl ?? defaultBackendUrl}/upload_image');
      
      // Create multipart request
      final request = http.MultipartRequest('POST', url);
      
      // Add form fields
      request.fields['session_id'] = sessionId;
      request.fields['user_question'] = userQuestion ?? 'Please help me with my homework';
      
      // Add image file
      final imageStream = http.ByteStream(imageFile.openRead());
      final imageLength = await imageFile.length();
      
      final multipartFile = http.MultipartFile(
        'image',
        imageStream,
        imageLength,
        filename: 'homework_image.jpg',
      );
      
      request.files.add(multipartFile);
      
      print('Uploading image to: $url');
      print('Session ID: $sessionId');
      print('Image size: $imageLength bytes');
      
      // Send request
      final response = await request.send();
      
      // Get response body
      final responseBody = await response.stream.bytesToString();
      
      print('Upload response status: ${response.statusCode}');
      print('Upload response body: $responseBody');
      
      if (response.statusCode == 200) {
        final result = json.decode(responseBody);
        return {
          'success': true,
          'data': result,
        };
      } else {
        return {
          'success': false,
          'error': 'HTTP ${response.statusCode}: $responseBody',
        };
      }
      
    } catch (e) {
      print('Error uploading image: $e');
      return {
        'success': false,
        'error': 'Upload failed: $e',
      };
    }
  }
}