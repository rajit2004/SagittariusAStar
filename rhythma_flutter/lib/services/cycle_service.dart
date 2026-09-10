import 'package:dio/dio.dart';
import '../models/cycle_log.dart';
import 'api_client.dart';
import 'offline_sync_service.dart';

class CycleService {
  final _dio = ApiClient.dio;

  Future<bool> submitLog(CycleLog log) async {
    try {
      await _dio.post('/cycle/log', data: log.toJson());
      return true;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await OfflineSyncService.enqueueUpsert(
          dateKey: log.toJson()['start_date'] as String,
          payload: log.toJson(),
        );
        return false;
      }
      rethrow;
    }
  }

  Future<bool> deleteLog(String logId) async {
    try {
      await _dio.delete('/cycle/$logId');
      return true;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await OfflineSyncService.enqueueDelete(dateKey: logId);
        return false;
      }
      rethrow;
    }
  }

  static bool _isNetworkError(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.unknown;
  }

  Future<Map<String, dynamic>> getCycleHistory(String userId, {int offset = 0, int limit = 15}) async {
    final response = await _dio.get(
      '/cycle/$userId/history',
      queryParameters: {
        'offset': offset,
        'limit': limit,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>?> getPrediction() async {
    try {
      final response = await _dio.get('/cycle/predictions');
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      if (_isNetworkError(e)) return null;
      rethrow;
    }
  }
}
