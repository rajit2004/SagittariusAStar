import 'package:flutter/material.dart';
import '../config/supported_languages.dart';
import '../services/local_storage_service.dart';
import '../services/user_settings_service.dart';

class LocaleProvider extends ChangeNotifier {
  Locale _locale;

  LocaleProvider() : _locale = Locale(LocalStorageService.preferredLanguage);

  Locale get locale => _locale;

  void setLocale(Locale locale) {
    if (!appSupportedLanguages.any((l) => l.code == locale.languageCode)) return;
    _locale = locale;
    LocalStorageService.setPreferredLanguage(locale.languageCode);
    notifyListeners();
    UserSettingsService.saveSettings({'language': locale.languageCode});
  }

  Future<void> reloadFromHive() async {
    final langCode = LocalStorageService.preferredLanguage;
    if (langCode != _locale.languageCode &&
        appSupportedLanguages.any((l) => l.code == langCode)) {
      _locale = Locale(langCode);
      notifyListeners();
    }
  }

  Future<void> applyServerSettings(Map<String, dynamic> settings) async {
    if (settings.containsKey('language')) {
      final langCode = settings['language'] as String;
      if (langCode.isNotEmpty && langCode != _locale.languageCode) {
        if (appSupportedLanguages.any((l) => l.code == langCode)) {
          _locale = Locale(langCode);
          LocalStorageService.setPreferredLanguage(langCode);
          notifyListeners();
        }
      }
    }
  }
}
