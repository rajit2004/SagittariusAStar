import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import '../utils/secure_storage.dart';
import '../config/app_config.dart';
import 'api_retry.dart';

const _publicEndpoints = {
  '/auth/login',
  '/auth/register',
  '/auth/firebase-login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/password-requirements',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/assistant/languages',
  '/health',
};

bool _isPublicEndpoint(String path) {
  for (final public in _publicEndpoints) {
    if (path == public || path.endsWith(public)) return true;
  }
  return false;
}

bool _isRetryableAuthPost(String? method, String path) {
  if ((method ?? '').toLowerCase() != 'post') return false;
  const retryable = {'/auth/login', '/auth/register', '/auth/refresh'};
  return retryable.any((p) => path == p || path.endsWith(p));
}

const String kRetryCountKey = 'rhythma.retryCount';

class ApiClient {
  static final Dio _dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: kDefaultTimeout,
    receiveTimeout: kDefaultTimeout,
    
    sendTimeout: kDefaultTimeout,
  ));

  static void Function()? _onUnauthorized;
  static bool _initialized = false;

  static Future<String>? _refreshFuture;

  static RetryPolicy retryPolicy = const RetryPolicy(
    isOffline: _deviceIsOffline,
  );

  static Future<bool> _deviceIsOffline() async {
    final results = await Connectivity().checkConnectivity();
    return results.isEmpty ||
        results.every((result) => result == ConnectivityResult.none);
  }

  static void init({void Function()? onUnauthorized}) {
    _onUnauthorized = onUnauthorized;
    if (_initialized) return;
    _initialized = true;
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await SecureStorage.getToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          final deadline = retryPolicy.timeoutFor(options.path);
          options.connectTimeout = deadline;
          options.receiveTimeout = deadline;
          options.sendTimeout = deadline;

          return handler.next(options);
        },
        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;
          final requestPath = error.requestOptions.path;

          if (statusCode != 401) {

            final attempt =
                (error.requestOptions.extra[kRetryCountKey] as int?) ?? 0;

            // Cold-start safety: the backend sleeps on Railway and the first
            // request can exceed normal timeouts. Auth POSTs are safe to
            // attempt once more when the failure was purely transport-level
            // (no response was ever received).
            final coldStartAuthRetry = attempt < 1 &&
                retryPolicy.isNetworkError(error) &&
                _isRetryableAuthPost(
                  error.requestOptions.method,
                  error.requestOptions.path,
                );

            if (retryPolicy.shouldRetry(error, attempt) ||
                coldStartAuthRetry) {
              
              if (await retryPolicy.shouldSuppressForOffline()) {
                return handler.next(error);
              }

              final retryAfter =
                  parseRetryAfter(retryAfterHeaderOf(error.response));
              await Future<void>.delayed(
                retryPolicy.backoffDelay(attempt, retryAfter: retryAfter),
              );

              final retryOptions = error.requestOptions
                ..extra[kRetryCountKey] = attempt + 1;

              try {
                final response = await _dio.fetch(retryOptions);
                return handler.resolve(response);
              } on DioException catch (retryError) {
                return handler.next(retryError);
              }
            }

            return handler.next(error);
          }

          if (_isPublicEndpoint(requestPath)) {
            return handler.next(error);
          }

          if (error.requestOptions.headers[kRetryAfterRefreshHeader] == '1') {
            await _forceReauthentication();
            return handler.next(error);
          }

          final refreshToken = await SecureStorage.getRefreshToken();
          if (refreshToken == null || refreshToken.isEmpty) {
            await _forceReauthentication();
            return handler.next(error);
          }

          final String newToken;
          try {
            newToken = await _performRefresh(refreshToken);
          } catch (_) {
            
            await _forceReauthentication();
            return handler.next(error);
          }

          final retryOptions = error.requestOptions.copyWith(
            headers: {
              ...error.requestOptions.headers,
              'Authorization': 'Bearer $newToken',
              kRetryAfterRefreshHeader: '1',
            },
          );

          try {
            final response = await _dio.fetch(retryOptions);
            return handler.resolve(response);
          } on DioException catch (retryError) {
            return handler.next(retryError);
          }
        },
      ),
    );
  }

  static Future<void> _forceReauthentication() async {
    await SecureStorage.clearAuth();
    _onUnauthorized?.call();
  }

  static Future<String> _performRefresh(String refreshToken) async {
    
    final inFlight = _refreshFuture;
    if (inFlight != null) {
      return inFlight;
    }

    final future = _doRefresh(refreshToken);
    _refreshFuture = future;
    try {
      return await future;
    } finally {
      _refreshFuture = null;
    }
  }

  static Future<String> _doRefresh(String refreshToken) async {
    final response = await _dio.post(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    final data = response.data;
    final newAccessToken = data is Map ? data['access_token'] : null;
    final newRefreshToken = data is Map ? data['refresh_token'] : null;

    if (newAccessToken is! String || newAccessToken.isEmpty) {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
        error: 'Refresh response carried no access token.',
      );
    }

    await SecureStorage.saveToken(newAccessToken);
    if (newRefreshToken is String && newRefreshToken.isNotEmpty) {
      
      await SecureStorage.saveRefreshToken(newRefreshToken);
    }

    return newAccessToken;
  }

  static Dio get dio => _dio;
}
