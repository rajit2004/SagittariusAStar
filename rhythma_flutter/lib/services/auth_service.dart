import 'package:dio/dio.dart';
import '../utils/secure_storage.dart';
import 'api_client.dart';
import 'firestore_service.dart';
import 'local_storage_service.dart';
import 'user_settings_service.dart';

class AuthService {
  final Dio _dio = ApiClient.dio;

  Future<String> login(String email, String password) async {
    try {
      final response = await _dio.post(
        '/auth/login',
        data: {'email': email, 'password': password},
      );
      final token = response.data['access_token'] as String;
      await SecureStorage.saveToken(token);

      final refreshToken = response.data['refresh_token'] as String?;
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await SecureStorage.saveRefreshToken(refreshToken);
      }

      try {
        final me = await _dio.get('/auth/me');
        final uid = (me.data as Map<String, dynamic>)['id']?.toString();
        if (uid != null) {
          await LocalStorageService.setCurrentUserId(uid);
          await _syncProfile(uid);
          await _syncSettingsFromServer();
          FirestoreService.pullCycleLogs(userId: uid);
          FirestoreService.pullProfile(userId: uid);
          FirestoreService.syncCycleLogs(userId: uid);
          FirestoreService.syncProfile(userId: uid);
        }
      } catch (_) {}

      return token;
    } on DioException catch (e) {
      throw AuthException(_readErrorMessage(e, 'Login failed. Please check your credentials.'));
    }
  }

  Future<String> register({
    required String email,
    required String password,
    String? fullName,
    String? username,
  }) async {
    try {
      final response = await _dio.post(
        '/auth/register',
        data: {
          'email': email,
          'password': password,
          if (fullName != null && fullName.isNotEmpty) 'full_name': fullName,
          if (username != null && username.isNotEmpty) 'username': username,
        },
      );
      final userId = response.data['id']?.toString();
      if (userId != null) {
        await LocalStorageService.setCurrentUserId(userId);
      }
      return await login(email, password);
    } on DioException catch (e) {
      throw AuthException(_readErrorMessage(e, 'Registration failed. Please try again.'));
    }
  }

  Future<String> firebaseLogin(String idToken) async {
    try {
      final response = await _dio.post(
        '/auth/firebase-login',
        data: {
          'id_token': idToken,
        },
      );
      final token = response.data['access_token'] as String;
      await SecureStorage.saveToken(token);

      final refreshToken = response.data['refresh_token'] as String?;
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await SecureStorage.saveRefreshToken(refreshToken);
      }

      try {
        final me = await _dio.get('/auth/me');
        final uid = (me.data as Map<String, dynamic>)['id']?.toString();
        if (uid != null) {
          await LocalStorageService.setCurrentUserId(uid);
          await _syncProfile(uid);
          await _syncSettingsFromServer();

          FirestoreService.pullCycleLogs(userId: uid);
          FirestoreService.pullProfile(userId: uid);
          FirestoreService.syncCycleLogs(userId: uid);
          FirestoreService.syncProfile(userId: uid);
        }
      } catch (_) {
        
      }

      return token;
    } on DioException catch (e) {
      throw AuthException(
          _readErrorMessage(e, 'Login failed. Please check your details.'));
    }
  }

  Future<void> _syncProfile(String uid) async {
    try {
      final profileResponse = await _dio.get('/auth/profile');
      if (profileResponse.statusCode == 200 && profileResponse.data is Map) {
        final profile = Map<String, dynamic>.from(profileResponse.data as Map);
        if (profile['cycle_length'] != null) {
          await LocalStorageService.setOnboardingCompleted(true);
          final localProfile = <String, dynamic>{
            'name': profile['full_name'] ?? 'User',
            'avatar': profile['avatar'] ?? 'assets/avatars/avatar_1.png',
            'language': profile['language'] ?? 'en',
          };
          if (profile['age'] != null) localProfile['age'] = profile['age'];
          if (profile['height_cm'] != null) {
            localProfile['height_cm'] = profile['height_cm'];
          }
          if (profile['weight_kg'] != null) {
            localProfile['weight_kg'] = profile['weight_kg'];
          }
          if (profile['last_period'] != null) {
            localProfile['last_period'] = profile['last_period'];
          }
          if (profile['last_period_is_approximate'] != null) {
            localProfile['last_period_is_approximate'] =
                profile['last_period_is_approximate'];
          }
          if (profile['cycle_length'] != null) {
            localProfile['cycle_length'] = profile['cycle_length'];
          }
          if (profile['period_duration'] != null) {
            localProfile['period_duration'] = profile['period_duration'];
          }
          if (profile['cycle_regular'] != null) {
            localProfile['cycle_regular'] = profile['cycle_regular'];
          }
          if (profile['phone'] != null) {
            localProfile['phone'] = profile['phone'];
          }
          if (profile['city'] != null) {
            localProfile['city'] = profile['city'];
          }
          if (profile['state'] != null) {
            localProfile['state'] = profile['state'];
          }
          if (profile['notifications_enabled'] != null) {
            localProfile['notifications_enabled'] =
                profile['notifications_enabled'];
          }
          await LocalStorageService.saveProfile(localProfile);
        }
      }
    } catch (_) {
      
    }
  }

  Future<void> logout() async {
    await SecureStorage.clearAuth();
    
    await LocalStorageService.setCurrentUserId(null);
  }

  Future<void> deleteAccount() async {
    try {
      await _dio.delete('/auth/me');
    } catch (_) {
      
    }
    await SecureStorage.clearAuth();
    await LocalStorageService.deleteCurrentUserData();
  }

  Future<bool> isLoggedIn() async {
    return await SecureStorage.hasToken();
  }

  Future<String?> validateSession() async {
    if (!await SecureStorage.hasToken()) return null;

    try {
      final response = await _dio.get('/auth/me');
      final uid = (response.data as Map<String, dynamic>)['id']?.toString();
      if (uid != null) {
        await LocalStorageService.setCurrentUserId(uid);
        await _syncProfile(uid);

        FirestoreService.pullCycleLogs(userId: uid);
        FirestoreService.pullProfile(userId: uid);
        FirestoreService.syncCycleLogs(userId: uid);
        FirestoreService.syncProfile(userId: uid);

        await _syncSettingsFromServer();
      }
      return uid;
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        await SecureStorage.clearAuth();
        return null;
      }

      return LocalStorageService.currentUserId;
    }
  }

  Future<void> _syncSettingsFromServer() async {
    try {
      final settings = await UserSettingsService.getSettings();
      if (settings.isNotEmpty) {
        if (settings.containsKey('primary_color')) {
          await LocalStorageService.setPrimaryColor(settings['primary_color'] as int);
        }
        if (settings.containsKey('dark_mode')) {
          await LocalStorageService.setThemeMode(
            (settings['dark_mode'] as bool) ? 'dark' : 'light',
          );
        }
        if (settings.containsKey('language')) {
          await LocalStorageService.setPreferredLanguage(settings['language'] as String);
        }
      }
    } catch (_) {}
  }

  Future<Map<String, dynamic>> getSettingsFromServer() async {
    return UserSettingsService.getSettings();
  }

  String _readErrorMessage(DioException error, String fallback) {
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.sendTimeout ||
        error.type == DioExceptionType.receiveTimeout) {
      return 'Request timed out. Please try again.';
    }

    if (error.type == DioExceptionType.connectionError) {
      return 'Network unavailable. Please check your internet connection.';
    }

    final response = error.response;
    if (response != null) {
      final data = response.data;
      if (data is Map<String, dynamic>) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) return detail;
        if (detail is List && detail.isNotEmpty) return detail.first.toString();
      }

      if (response.statusCode == 401) {
        return 'Invalid credentials. Please verify your username and password.';
      }
      if (response.statusCode == 404) {
        return 'Profile lookup failed. Resource not found.';
      }
      if (response.statusCode != null && response.statusCode! >= 500) {
        return 'Server error (${response.statusCode}). Please try again later.';
      }
    }

    return fallback;
  }
}

class AuthException implements Exception {
  final String message;

  const AuthException(this.message);

  @override
  String toString() => message;
}
