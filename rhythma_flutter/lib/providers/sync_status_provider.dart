import 'package:flutter/material.dart';

enum SyncStatus {
  synced,      
  syncing,     
  pending,     
  offline,     
  error,       
}

class SyncStatusProvider extends ChangeNotifier {
  static SyncStatusProvider? _instance;
  static SyncStatusProvider get instance => _instance!;
  static bool get hasInstance => _instance != null;

  SyncStatusProvider() {
    _instance = this;
  }

  SyncStatus _cycleStatus = SyncStatus.synced;
  SyncStatus _profileStatus = SyncStatus.synced;
  String? _cycleError;
  String? _profileError;
  DateTime? _lastSyncTime;

  SyncStatus get cycleStatus => _cycleStatus;
  SyncStatus get profileStatus => _profileStatus;
  String? get cycleError => _cycleError;
  String? get profileError => _profileError;
  DateTime? get lastSyncTime => _lastSyncTime;

  SyncStatus get overallStatus {
    if (_cycleStatus == SyncStatus.syncing || _profileStatus == SyncStatus.syncing) {
      return SyncStatus.syncing;
    }
    if (_cycleStatus == SyncStatus.error || _profileStatus == SyncStatus.error) {
      return SyncStatus.error;
    }
    if (_cycleStatus == SyncStatus.pending || _profileStatus == SyncStatus.pending) {
      return SyncStatus.pending;
    }
    if (_cycleStatus == SyncStatus.offline || _profileStatus == SyncStatus.offline) {
      return SyncStatus.offline;
    }
    return SyncStatus.synced;
  }

  void updateStatus(SyncStatus status, String type, {String? error}) {
    switch (type) {
      case 'cycle':
        _cycleStatus = status;
        _cycleError = error;
        break;
      case 'profile':
        _profileStatus = status;
        _profileError = error;
        break;
    }
    if (status == SyncStatus.synced) {
      _lastSyncTime = DateTime.now();
    }
    notifyListeners();
  }

  void setOffline() {
    _cycleStatus = SyncStatus.offline;
    _profileStatus = SyncStatus.offline;
    notifyListeners();
  }

  void setOnline() {
    _cycleStatus = SyncStatus.pending;
    _profileStatus = SyncStatus.pending;
    notifyListeners();
  }
}
