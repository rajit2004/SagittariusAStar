import 'package:flutter/material.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';
import '../services/user_settings_service.dart';

class ThemeProvider extends ChangeNotifier {
  Color _primaryColor = const Color(0xFF9B72CF);
  bool _isDarkMode = false;

  Color get primaryColor => _primaryColor;
  bool get isDarkMode => _isDarkMode;
  ThemeMode get themeMode => _isDarkMode ? ThemeMode.dark : ThemeMode.light;

  ThemeProvider() {
    _loadTheme();
  }

  ThemeData? get theme => null;

  Future<void> _loadTheme() async {
    String? modeStr = LocalStorageService.getThemeMode();
    if (modeStr != null) {
      _isDarkMode = modeStr == 'dark';
    }

    int? colorVal = LocalStorageService.getPrimaryColor();
    if (colorVal != null) {
      _primaryColor = Color(colorVal);
    }

    RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
    notifyListeners();
  }

  Future<void> setDarkMode(bool isDark) async {
    _isDarkMode = isDark;
    RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
    await LocalStorageService.setThemeMode(isDark ? 'dark' : 'light');
    notifyListeners();
    _syncToServer();
  }

  Future<void> setPrimaryColor(Color color) async {
    _primaryColor = color;
    RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
    await LocalStorageService.setPrimaryColor(color.toARGB32());
    notifyListeners();
    _syncToServer();
  }

  Future<void> applyServerSettings(Map<String, dynamic> settings) async {
    bool changed = false;

    if (settings.containsKey('dark_mode')) {
      final darkMode = settings['dark_mode'] as bool;
      if (darkMode != _isDarkMode) {
        _isDarkMode = darkMode;
        await LocalStorageService.setThemeMode(darkMode ? 'dark' : 'light');
        changed = true;
      }
    }

    if (settings.containsKey('primary_color')) {
      final colorVal = settings['primary_color'] as int;
      final color = Color(colorVal);
      if (color != _primaryColor) {
        _primaryColor = color;
        await LocalStorageService.setPrimaryColor(colorVal);
        changed = true;
      }
    }

    if (changed) {
      RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
      notifyListeners();
    }
  }

  Future<void> reloadFromHive() async {
    String? modeStr = LocalStorageService.getThemeMode();
    final newDark = modeStr == 'dark';

    int? colorVal = LocalStorageService.getPrimaryColor();
    final newColor = colorVal != null ? Color(colorVal) : const Color(0xFF9B72CF);

    if (newDark != _isDarkMode || newColor != _primaryColor) {
      _isDarkMode = newDark;
      _primaryColor = newColor;
      RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
      notifyListeners();
    }
  }

  void _syncToServer() {
    UserSettingsService.saveSettings({
      'dark_mode': _isDarkMode,
      'primary_color': _primaryColor.toARGB32(),
    });
  }
}
