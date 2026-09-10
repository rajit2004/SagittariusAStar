import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'api_client.dart';
import 'local_storage_service.dart';
import '../providers/sync_status_provider.dart';

class OfflineSyncService {
  static const String _boxName = 'offline_queue';

  static Box<Map>? _box;
  static StreamSubscription<List<ConnectivityResult>>?
      _connectivitySubscription;
  static final Connectivity _connectivity = Connectivity();
  static bool _initialized = false;
  static bool _flushing = false;

  static void _updateStatus(SyncStatus status, String type, {String? error}) {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.updateStatus(status, type, error: error);
    }
  }

  static Future<void> init() async {
    if (_initialized) return;

    _box = Hive.box<Map>(_boxName);

    _connectivitySubscription = _connectivity.onConnectivityChanged.listen(
      _onConnectivityChanged,
    );

    final uid = LocalStorageService.currentUserId;
    if (uid != null && hasPendingItems) {
      flushQueue(uid);
    }

    _initialized = true;
    debugPrint('OfflineSyncService: initialized');
  }

  static void _onConnectivityChanged(List<ConnectivityResult> results) {
    final isOnline = results.any((r) => r != ConnectivityResult.none);
    if (isOnline) {
      final uid = LocalStorageService.currentUserId;
      if (uid != null && hasPendingItems) {
        flushQueue(uid);
      }
    }
  }

  static bool get hasPendingItems => _box != null && _box!.isNotEmpty;

  static int get pendingCount => _box?.length ?? 0;

  static Future<void> enqueueUpsert({
    required String dateKey,
    required Map<String, dynamic> payload,
  }) async {
    if (_box == null) return;
    final uid = LocalStorageService.currentUserId;
    if (uid == null) return;

    final key = 'upsert::$uid::$dateKey';
    await _box!.put(key, {
      'type': 'upsert',
      'date_key': dateKey,
      'payload': payload,
      'user_id': uid,
      'created_at': DateTime.now().toIso8601String(),
    });
    _updateStatus(SyncStatus.pending, 'cycle');
    debugPrint('OfflineSyncService: enqueued upsert for $dateKey');
  }

  static Future<void> enqueueDelete({
    required String dateKey,
  }) async {
    if (_box == null) return;
    final uid = LocalStorageService.currentUserId;
    if (uid == null) return;

    final key = 'delete::$uid::$dateKey';
    await _box!.put(key, {
      'type': 'delete',
      'date_key': dateKey,
      'user_id': uid,
      'created_at': DateTime.now().toIso8601String(),
    });
    _updateStatus(SyncStatus.pending, 'cycle');
    debugPrint('OfflineSyncService: enqueued delete for $dateKey');
  }

  static Future<void> flushQueue(String userId) async {
    if (_box == null || _box!.isEmpty || _flushing) return;

    _flushing = true;
    _updateStatus(SyncStatus.syncing, 'cycle');

    try {
      final allKeys = _box!.keys.toList();

      final upsertKeys = allKeys.where((k) => k.toString().startsWith('upsert::$userId')).toList();
      final deleteKeys = allKeys.where((k) => k.toString().startsWith('delete::$userId')).toList();

      if (upsertKeys.isNotEmpty) {
        await _flushUpserts(upsertKeys);
      }

      if (deleteKeys.isNotEmpty) {
        await _flushDeletes(deleteKeys);
      }

      if (_box!.isEmpty) {
        _updateStatus(SyncStatus.synced, 'cycle');
      } else {
        _updateStatus(SyncStatus.pending, 'cycle');
      }

      debugPrint('OfflineSyncService: flush complete');
    } catch (e) {
      debugPrint('OfflineSyncService: flush failed: $e');
      _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
    } finally {
      _flushing = false;
    }
  }

  static Future<void> _flushUpserts(List<dynamic> keys) async {
    final dio = ApiClient.dio;
    final items = <Map<String, dynamic>>[];

    for (final key in keys) {
      final entry = _box!.get(key);
      if (entry == null) continue;
      items.add({
        'start_date': entry['date_key'],
        ...Map<String, dynamic>.from(entry['payload'] as Map),
      });
    }

    if (items.isEmpty) return;

    try {
      final response = await dio.post('/cycle/batch', data: {'items': items});
      final results = (response.data['results'] as List).cast<Map<String, dynamic>>();

      for (int i = 0; i < keys.length; i++) {
        final result = i < results.length ? results[i] : null;
        if (result != null && result['status'] == 'ok') {
          await _box!.delete(keys[i]);
        }
      }
    } catch (e) {
      debugPrint('OfflineSyncService: batch upsert failed: $e');
      rethrow;
    }
  }

  static Future<void> _flushDeletes(List<dynamic> keys) async {
    final dio = ApiClient.dio;
    final dateKeys = <String>[];

    for (final key in keys) {
      final entry = _box!.get(key);
      if (entry == null) continue;
      dateKeys.add(entry['date_key'] as String);
    }

    if (dateKeys.isEmpty) return;

    try {
      final response = await dio.post('/cycle/batch-delete', data: {'date_keys': dateKeys});
      final results = (response.data['results'] as List).cast<Map<String, dynamic>>();

      for (int i = 0; i < keys.length; i++) {
        final result = i < results.length ? results[i] : null;
        if (result != null && result['status'] == 'ok') {
          await _box!.delete(keys[i]);
        }
      }
    } catch (e) {
      debugPrint('OfflineSyncService: batch delete failed: $e');
      rethrow;
    }
  }

  static void dispose() {
    _connectivitySubscription?.cancel();
  }
}
