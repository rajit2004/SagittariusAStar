import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'local_storage_service.dart';
import '../providers/sync_status_provider.dart';

class FirestoreService {
  static FirebaseFirestore? _db;
  static StreamSubscription<List<ConnectivityResult>>?
      _connectivitySubscription;
  static final Connectivity _connectivity = Connectivity();
  static bool _initialized = false;
  static bool _isSyncing = false;

  static void _updateStatus(SyncStatus status, String type, {String? error}) {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.updateStatus(status, type, error: error);
    }
  }

  static void _setOnline() {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.setOnline();
    }
  }

  static void _setOffline() {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.setOffline();
    }
  }

  static Future<void> init() async {
    if (_initialized) return;

    _db = FirebaseFirestore.instance;
    _db!.settings = const Settings(
      persistenceEnabled: true,
      cacheSizeBytes: Settings.CACHE_SIZE_UNLIMITED,
    );

    _connectivitySubscription = _connectivity.onConnectivityChanged.listen(
      _onConnectivityChanged,
    );

    final results = await _connectivity.checkConnectivity();
    _onConnectivityChanged(results);

    _initialized = true;
    debugPrint('FirestoreService: initialized with offline persistence');
  }

  static void _onConnectivityChanged(List<ConnectivityResult> results) {
    final isOnline = results.any((r) => r != ConnectivityResult.none);

    if (isOnline) {
      _setOnline();
      
      final uid = LocalStorageService.currentUserId;
      if (uid != null && LocalStorageService.cloudSyncEnabled) {
        flushPendingQueue(uid);
        syncCycleLogs(userId: uid);
        syncProfile(userId: uid);
      }
    } else {
      _setOffline();
    }
  }

  static Future<void> syncCycleLogs({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) {
      debugPrint('FirestoreService: cloud sync disabled, skipping cycle sync');
      _updateStatus(SyncStatus.synced, 'cycle');
      return;
    }
    if (_db == null || _isSyncing) return;

    final logs = LocalStorageService.getCycleLogs();
    if (logs.isEmpty) {
      debugPrint('FirestoreService: no local cycle logs to sync');
      _updateStatus(SyncStatus.synced, 'cycle');
      return;
    }

    _isSyncing = true;
    _updateStatus(SyncStatus.syncing, 'cycle');

    try {
      final batch = _db!.batch();
      final userRef = _db!.collection('client_sync').doc(userId);

      for (final log in logs) {
        final docRef =
            userRef.collection('cycle_logs').doc(log['start_date'] as String);
        final data = Map<String, dynamic>.from(log);
        
        data['synced_at'] = FieldValue.serverTimestamp();
        data['user_id'] = LocalStorageService.currentUserId;
        batch.set(docRef, data, SetOptions(merge: true));
      }

      await batch.commit();
      debugPrint(
          'FirestoreService: synced ${logs.length} cycle logs for $userId');

      for (final log in logs) {
        final docRef =
            userRef.collection('cycle_logs').doc(log['start_date'] as String);
        final doc = await docRef.get();
        if (doc.exists) {
          final resolvedData = doc.data()!;
          resolvedData['start_date'] = log['start_date'];
          await LocalStorageService.saveCycleLog(resolvedData);
        }
      }

      _updateStatus(SyncStatus.synced, 'cycle');
    } catch (e) {
      debugPrint('FirestoreService: cycle sync failed: $e');
      _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
      
      await _queuePendingCycleLogs(userId, logs);
    } finally {
      _isSyncing = false;
    }
  }

  static Future<void> pullCycleLogs(
      {required String userId, int limit = 50}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    try {
      final snapshot = await _db!
          .collection('client_sync')
          .doc(userId)
          .collection('cycle_logs')
          .orderBy('start_date', descending: true)
          .limit(limit)
          .get();

      for (final doc in snapshot.docs) {
        final data = doc.data();
        final localLog =
            LocalStorageService.getCycleLogForDate(DateTime.parse(doc.id));

        final serverTime = data['synced_at'] as Timestamp?;
        final localTime = localLog?['synced_at'] as Timestamp?;

        if (serverTime != null &&
            (localTime == null || serverTime.compareTo(localTime) >= 0)) {
          
          data['start_date'] = doc.id; 
          await LocalStorageService.saveCycleLog(data);
        }
      }
      debugPrint(
          'FirestoreService: pulled ${snapshot.docs.length} cycle logs for $userId');
      _updateStatus(SyncStatus.synced, 'cycle');
    } catch (e) {
      debugPrint('FirestoreService: pull cycle logs failed: $e');
      _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
    }
  }

  static Future<void> _queuePendingCycleLogs(
      String userId, List<Map<String, dynamic>> logs) async {
    final pendingBox = Hive.box<Map>('pending_cycle_sync');
    for (final log in logs) {
      final key = 'cycle::$userId::${log['start_date']}';
      await pendingBox.put(key, {
        ...log,
        'type': 'cycle',
        'user_id': userId,
        'queued_at': DateTime.now().toIso8601String()
      });
    }
    _updateStatus(SyncStatus.pending, 'cycle');
  }

  static Future<void> _queuePendingProfile(
      String userId, Map<String, dynamic> profile) async {
    final pendingBox = Hive.box<Map>('pending_cycle_sync');
    final key = 'profile::$userId';
    await pendingBox.put(key, {
      ...profile,
      'type': 'profile',
      'user_id': userId,
      'queued_at': DateTime.now().toIso8601String()
    });
    _updateStatus(SyncStatus.pending, 'profile');
  }

  static Future<void> flushPendingQueue(String userId) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    final pendingBox = Hive.box<Map>('pending_cycle_sync');
    final keys = pendingBox.keys
        .where((k) => k.toString().contains('::$userId'))
        .toList();

    if (keys.isEmpty) return;

    debugPrint(
        'FirestoreService: flushing ${keys.length} pending items for $userId');

    final cycleKeys = keys.where((k) => !k.startsWith('profile::')).toList();
    if (cycleKeys.isNotEmpty) {
      _updateStatus(SyncStatus.syncing, 'cycle');
      try {
        final batch = _db!.batch();
        final userRef = _db!.collection('client_sync').doc(userId);

        for (final key in cycleKeys) {
          final log = pendingBox.get(key)!;
          if (log['type'] != 'cycle') continue;
          final docRef =
              userRef.collection('cycle_logs').doc(log['start_date'] as String);
          final data = Map<String, dynamic>.from(log);
          data.remove('type');
          data.remove('user_id');
          data.remove('queued_at');
          data['synced_at'] = FieldValue.serverTimestamp();
          data['user_id'] = LocalStorageService.currentUserId;
          batch.set(docRef, data, SetOptions(merge: true));
        }

        await batch.commit();

        for (final key in cycleKeys) {
          await pendingBox.delete(key);
        }

        debugPrint(
            'FirestoreService: flushed ${cycleKeys.length} pending cycle logs for $userId');
        _updateStatus(SyncStatus.synced, 'cycle');
      } catch (e) {
        debugPrint('FirestoreService: flush cycle queue failed: $e');
        _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
      }
    }

    final profileKey = 'profile::$userId';
    if (keys.contains(profileKey)) {
      _updateStatus(SyncStatus.syncing, 'profile');
      try {
        final profileData = pendingBox.get(profileKey)!;
        final userRef = _db!.collection('client_sync').doc(userId);
        final data = Map<String, dynamic>.from(profileData);
        data.remove('type');
        data.remove('user_id');
        data.remove('queued_at');
        data['synced_at'] = FieldValue.serverTimestamp();
        data['user_id'] = LocalStorageService.currentUserId;

        await userRef.set(data, SetOptions(merge: true));

        await pendingBox.delete(profileKey);

        debugPrint('FirestoreService: flushed pending profile for $userId');
        _updateStatus(SyncStatus.synced, 'profile');
      } catch (e) {
        debugPrint('FirestoreService: flush profile queue failed: $e');
        _updateStatus(SyncStatus.error, 'profile', error: e.toString());
      }
    }
  }

  static Future<void> syncProfile({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    final profile = LocalStorageService.getProfile();
    if (profile == null) return;

    _updateStatus(SyncStatus.syncing, 'profile');

    try {
      final userRef = _db!.collection('client_sync').doc(userId);
      final data = Map<String, dynamic>.from(profile);
      data['synced_at'] = FieldValue.serverTimestamp();
      data['user_id'] = LocalStorageService.currentUserId;

      await userRef.set(data, SetOptions(merge: true));
      debugPrint('FirestoreService: synced profile for $userId');

      final resolvedDoc = await userRef.get();
      if (resolvedDoc.exists) {
        final resolved = resolvedDoc.data()!;
        final merged = {...profile, ...resolved};
        await LocalStorageService.saveProfile(merged);
      }

      _updateStatus(SyncStatus.synced, 'profile');
    } catch (e) {
      debugPrint('FirestoreService: profile sync failed: $e');
      _updateStatus(SyncStatus.error, 'profile', error: e.toString());
      await _queuePendingProfile(userId, profile);
    }
  }

  static Future<void> pullProfile({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    try {
      final doc = await _db!.collection('client_sync').doc(userId).get();
      if (!doc.exists) return;

      final data = doc.data()!;
      final localProfile = LocalStorageService.getProfile() ?? {};

      final serverTime = data['synced_at'] as Timestamp?;
      final localTime = localProfile['synced_at'] as Timestamp?;

      if (serverTime != null &&
          (localTime == null || serverTime.compareTo(localTime) >= 0)) {
        
        final merged = {...localProfile, ...data};
        await LocalStorageService.saveProfile(merged);
      }

      debugPrint('FirestoreService: pulled profile for $userId');
      _updateStatus(SyncStatus.synced, 'profile');
    } catch (e) {
      debugPrint('FirestoreService: pull profile failed: $e');
      _updateStatus(SyncStatus.error, 'profile', error: e.toString());
    }
  }

  static Stream<QuerySnapshot<Map<String, dynamic>>> cycleLogsStream(
      String userId) {
    if (_db == null) return Stream.empty();
    return _db!
        .collection('client_sync')
        .doc(userId)
        .collection('cycle_logs')
        .orderBy('start_date', descending: true)
        .limit(50)
        .snapshots();
  }

  static Stream<DocumentSnapshot<Map<String, dynamic>>> profileStream(
      String userId) {
    if (_db == null) return Stream.empty();
    return _db!.collection('client_sync').doc(userId).snapshots();
  }

  static void dispose() {
    _connectivitySubscription?.cancel();
  }
}
