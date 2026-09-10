import 'package:dio/dio.dart';
import 'api_client.dart';

class ProfileService {
  static final Dio _dio = ApiClient.dio;

  static Future<void> patchProfile(Map<String, dynamic> data) async {
    try {
      
      final payload = _buildPayload(data);
      if (payload.isEmpty) return;
      await _dio.patch('/auth/profile', data: payload);
    } on DioException catch (_) {
      
    } catch (_) {
      
    }
  }

  static Future<Map<String, dynamic>?> fetchProfile() async {
    try {
      final response = await _dio.get('/auth/profile');
      if (response.statusCode == 200 && response.data is Map) {
        return Map<String, dynamic>.from(response.data as Map);
      }
      return null;
    } on DioException catch (_) {
      return null;
    } catch (_) {
      return null;
    }
  }

  static Map<String, dynamic> _buildPayload(Map<String, dynamic> data) {
    const allowed = {
      'full_name',
      'age',
      'height_cm',
      'weight_kg',
      'avatar',
      'language',
      'last_period',
      'last_period_is_approximate',
      'cycle_length',
      'period_duration',
      'cycle_regular',
      'notifications_enabled',
      'phone',
      'city',
      'state',
    };

    final payload = <String, dynamic>{};

    for (final key in allowed) {
      if (data.containsKey(key) && data[key] != null) {
        payload[key] = data[key];
      }
    }

    if (!payload.containsKey('full_name') &&
        data.containsKey('name') &&
        data['name'] != null) {
      payload['full_name'] = data['name'];
    }

    return payload;
  }
}
