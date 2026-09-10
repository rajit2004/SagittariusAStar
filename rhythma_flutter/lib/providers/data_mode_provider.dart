import 'package:flutter/foundation.dart';
import '../config/app_config.dart';

enum DataMode {
  
  live,

  dev,
}

class DataModeProvider extends ChangeNotifier {
  DataModeProvider() : _mode = _detectMode();

  static DataMode _detectMode() {
    const url = AppConfig.apiBaseUrl;
    if (url.contains('api.rhythma.app')) {
      return DataMode.live;
    }
    return DataMode.dev;
  }

  final DataMode _mode;

  DataMode get mode => _mode;

  bool get isLive => _mode == DataMode.live;

  bool get isDev => _mode == DataMode.dev;

  String get label {
    switch (_mode) {
      case DataMode.live:
        return 'Live Data';
      case DataMode.dev:
        return 'Dev Data';
    }
  }

  String get apiUrl => AppConfig.apiBaseUrl;
}
