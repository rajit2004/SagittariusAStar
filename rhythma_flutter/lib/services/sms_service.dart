import 'package:dio/dio.dart';
import 'api_client.dart';

class SmsService {
  final Dio _dio = ApiClient.dio;

  Future<Map<String, dynamic>> getSettings() async {
    final response = await _dio.get('/sms/settings');
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> saveSettings({
    required String phoneNumber,
    required bool enabled,
  }) async {
    final response = await _dio.post('/sms/settings', data: {
      'phoneNumber': phoneNumber,
      'enabled': enabled,
    });
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> sendSummary({
    required String phoneNumber,
    required String message,
  }) async {
    await _dio.post('/sms/send-summary', data: {
      'phone_number': phoneNumber,
      'message': message,
    });
  }
}
