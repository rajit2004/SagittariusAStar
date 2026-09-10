
library;

import 'dart:math';

import 'package:dio/dio.dart';

const Duration kDefaultTimeout = Duration(seconds: 10);

const Duration kLongTimeout = Duration(seconds: 45);

const List<String> kLongTimeoutPaths = ['/assistant/chat'];

const Set<int> kRetryableStatuses = {429, 502, 503, 504};

const Set<String> kRetryableMethods = {'get', 'head', 'options'};

const String kRetryAfterRefreshHeader = 'X-Retry-After-Refresh';

const Set<DioExceptionType> _transportFailures = {
  DioExceptionType.connectionTimeout,
  DioExceptionType.sendTimeout,
  DioExceptionType.receiveTimeout,
  DioExceptionType.connectionError,
  DioExceptionType.unknown,
};

class RetryPolicy {
  const RetryPolicy({
    this.maxAttempts = 3,
    this.baseBackoff = const Duration(milliseconds: 300),
    this.maxBackoff = const Duration(seconds: 5),
    this.defaultTimeout = kDefaultTimeout,
    this.longTimeout = kLongTimeout,
    this.random,
    this.isOffline,
  });

  final int maxAttempts;

  final Duration baseBackoff;

  final Duration maxBackoff;

  final Duration defaultTimeout;
  final Duration longTimeout;

  final double Function()? random;

  final Future<bool> Function()? isOffline;

  bool isRetryableMethod(String? method) =>
      kRetryableMethods.contains((method ?? 'get').toLowerCase());

  bool isNetworkError(DioException error) {
    if (error.response != null) return false;
    return _transportFailures.contains(error.type);
  }

  bool shouldRetry(DioException error, int attempt) {
    if (attempt >= maxAttempts) return false;
    if (!isRetryableMethod(error.requestOptions.method)) return false;

    if (error.requestOptions.headers[kRetryAfterRefreshHeader] == '1') {
      return false;
    }

    final status = error.response?.statusCode;
    if (status == null) return isNetworkError(error);
    return kRetryableStatuses.contains(status);
  }

  Duration backoffDelay(int attempt, {Duration? retryAfter}) {
    if (retryAfter != null) {
      final cap = maxBackoff * 4;
      return retryAfter > cap ? cap : retryAfter;
    }

    final exponential = baseBackoff * pow(2, attempt).toDouble();
    final ceiling = exponential > maxBackoff ? maxBackoff : exponential;
    final jitter = (random ?? Random().nextDouble)();

    return Duration(
      milliseconds: (ceiling.inMilliseconds * jitter).round(),
    );
  }

  Duration timeoutFor(String? path) {
    if (path == null || path.isEmpty) return defaultTimeout;
    final matches = kLongTimeoutPaths.any(path.contains);
    return matches ? longTimeout : defaultTimeout;
  }

  Future<bool> shouldSuppressForOffline() async {
    final check = isOffline;
    if (check == null) return false;
    try {
      return await check();
    } catch (_) {
      
      return false;
    }
  }
}

Duration? parseRetryAfter(String? value, {DateTime? now}) {
  if (value == null) return null;

  final trimmed = value.trim();
  if (trimmed.isEmpty) return null;

  if (RegExp(r'^\d+$').hasMatch(trimmed)) {
    return Duration(seconds: int.parse(trimmed));
  }

  final at = _parseHttpDate(trimmed);
  if (at == null) return null;

  final delta = at.difference((now ?? DateTime.now()).toUtc());
  return delta.isNegative ? Duration.zero : delta;
}

String? retryAfterHeaderOf(Response<dynamic>? response) {
  final values = response?.headers.map['retry-after'];
  if (values == null || values.isEmpty) return null;
  return values.first;
}

DateTime? _parseHttpDate(String value) {
  final match = RegExp(
    r'^[A-Za-z]{3},\s+(\d{2})\s+([A-Za-z]{3})\s+(\d{4})\s+'
    r'(\d{2}):(\d{2}):(\d{2})\s+GMT$',
  ).firstMatch(value);

  if (match != null) {
    final month = _months[match.group(2)!];
    if (month == null) return null;
    return DateTime.utc(
      int.parse(match.group(3)!),
      month,
      int.parse(match.group(1)!),
      int.parse(match.group(4)!),
      int.parse(match.group(5)!),
      int.parse(match.group(6)!),
    );
  }

  return DateTime.tryParse(value)?.toUtc();
}

const Map<String, int> _months = {
  'Jan': 1,
  'Feb': 2,
  'Mar': 3,
  'Apr': 4,
  'May': 5,
  'Jun': 6,
  'Jul': 7,
  'Aug': 8,
  'Sep': 9,
  'Oct': 10,
  'Nov': 11,
  'Dec': 12,
};
