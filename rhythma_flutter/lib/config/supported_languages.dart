import 'package:flutter/material.dart';

class SupportedLanguage {
  final String code;
  final String nativeName;

  const SupportedLanguage({
    required this.code,
    required this.nativeName,
  });

  Locale get locale => Locale(code);
}

const List<SupportedLanguage> appSupportedLanguages = [
  SupportedLanguage(code: 'en', nativeName: 'English'),
  SupportedLanguage(code: 'hi', nativeName: 'हिन्दी'),
  SupportedLanguage(code: 'ta', nativeName: 'தமிழ்'),
  SupportedLanguage(code: 'te', nativeName: 'తెలుగు'),
  SupportedLanguage(code: 'mr', nativeName: 'मराठी'),
  SupportedLanguage(code: 'gu', nativeName: 'ગુજરાતી'),
  SupportedLanguage(code: 'kn', nativeName: 'ಕನ್ನಡ'),
  SupportedLanguage(code: 'ml', nativeName: 'മലയാളം'),
];
