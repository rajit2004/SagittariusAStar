import 'api_client.dart';

class UserSettingsService {
  static Future<Map<String, dynamic>> getSettings() async {
    try {
      final response = await ApiClient.dio.get('/auth/settings');
      final data = response.data as Map<String, dynamic>;
      return (data['settings'] as Map<String, dynamic>?) ?? {};
    } catch (_) {
      return {};
    }
  }

  static Future<Map<String, dynamic>> saveSettings(Map<String, dynamic> settings) async {
    try {
      final response = await ApiClient.dio.put(
        '/auth/settings',
        data: settings,
      );
      final data = response.data as Map<String, dynamic>;
      return (data['settings'] as Map<String, dynamic>?) ?? {};
    } catch (_) {
      return {};
    }
  }
}
