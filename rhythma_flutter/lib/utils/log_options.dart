import 'package:rhythma/l10n/app_localizations.dart';

class LogOption {
  final String label;
  final String value;
  const LogOption(this.label, this.value);
}

class LogOptions {
  static List<LogOption> flow(AppLocalizations l10n) => [
        LogOption(l10n.logNone, 'none'),
        LogOption(l10n.logFlowSpotting, 'spotting'),
        LogOption(l10n.logLight, 'light'),
        LogOption(l10n.logMedium, 'medium'),
        LogOption(l10n.logHeavy, 'heavy'),
        LogOption(l10n.logFlowVeryHeavy, 'very_heavy'),
      ];

  static const List<LogOption> mood = [
    LogOption('😊', 'happy'),
    LogOption('😐', 'neutral'),
    LogOption('😔', 'sad'),
    LogOption('😤', 'frustrated'),
    LogOption('🥰', 'loved'),
  ];

  static List<LogOption> sleep(AppLocalizations l10n) => [
        LogOption(l10n.logSleep1, '4'),
        LogOption(l10n.logSleep2, '6'),
        LogOption(l10n.logSleep3, '8'),
        LogOption(l10n.logSleep4, '9.5'),
      ];

  static List<LogOption> stress(AppLocalizations l10n) => [
        LogOption(l10n.logEnergyLow, '1'),
        LogOption(l10n.logEnergyMid, '3'),
        LogOption(l10n.logEnergyHigh, '5'),
      ];

  static List<LogOption> symptoms(AppLocalizations l10n) => [
        LogOption(l10n.logSympCramps, 'cramps'),
        LogOption(l10n.logSympHeadache, 'headache'),
        LogOption(l10n.logSympBloating, 'bloating'),
        LogOption(l10n.logSympFatigue, 'fatigue'),
        LogOption(l10n.logSympNausea, 'nausea'),
        LogOption(l10n.logSympAcne, 'acne'),
        LogOption(l10n.logSympBackPain, 'back pain'),
        LogOption(l10n.logSympSeverePain, 'severe pain'),
        LogOption(l10n.logSympFainting, 'fainting'),
      ];
}
