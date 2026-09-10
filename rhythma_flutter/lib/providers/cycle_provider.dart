import 'package:flutter/material.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

class CycleProvider extends ChangeNotifier {
  final DateTime _today = DateTime.now();

  late DateTime _selectedDate;
  late DateTime _displayedMonth;

  CycleProvider() {
    _selectedDate = DateTime(_today.year, _today.month, _today.day);
    _displayedMonth = DateTime(_today.year, _today.month);
  }

  DateTime get selectedDate => _selectedDate;
  DateTime get displayedMonth => _displayedMonth;

  void selectDate(DateTime date) {
    final today = DateTime(_today.year, _today.month, _today.day);
    final normalized = DateTime(date.year, date.month, date.day);
    if (normalized.isAfter(today)) return; 
    if (_selectedDate != normalized) {
      _selectedDate = normalized;
      notifyListeners();
    }
  }

  void setDisplayedMonth(DateTime month) {
    if (_displayedMonth.year != month.year ||
        _displayedMonth.month != month.month) {
      _displayedMonth = DateTime(month.year, month.month);
      notifyListeners();
    }
  }

  void jumpToToday() {
    _displayedMonth = DateTime(_today.year, _today.month);
    _selectedDate = DateTime(_today.year, _today.month, _today.day);
    notifyListeners();
  }

  bool hasLogsForDate(DateTime date) {
    return LocalStorageService.getCycleLogForDate(date) != null;
  }

  void refresh() => notifyListeners();

  void refreshLogs() {
    notifyListeners();
  }

  int get _periodDuration {
    final profile = LocalStorageService.getProfile();
    return (profile?['period_duration'] as num?)?.toInt() ?? 5;
  }

  int get _cycleLength {
    final profile = LocalStorageService.getProfile();
    return (profile?['cycle_length'] as num?)?.toInt() ?? 28;
  }

  int _getCycleDay(DateTime date) {
    final profile = LocalStorageService.getProfile();
    final lastPeriodStr = profile?['last_period'] as String?;
    if (lastPeriodStr == null) return date.day;

    final lastPeriod = DateTime.tryParse(lastPeriodStr);
    if (lastPeriod == null) return date.day;

    final normalizedStart =
        DateTime(lastPeriod.year, lastPeriod.month, lastPeriod.day);
    final normalizedDate = DateTime(date.year, date.month, date.day);

    final daysSince = normalizedDate.difference(normalizedStart).inDays;
    final cycleLength = _cycleLength;
    if (cycleLength <= 0) return date.day;

    final cycleDay = ((daysSince % cycleLength) + cycleLength) % cycleLength;
    return cycleDay + 1;
  }

  String phaseKey(DateTime date) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return 'menstrual';
    if (day <= follicularEnd) return 'follicular';
    if (day <= ovulationEnd) return 'ovulation';
    return 'luteal';
  }

  String phase(DateTime date, AppLocalizations l10n) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return l10n.cyclePhasePeriod;
    if (day <= follicularEnd) return l10n.cyclePhaseFollicular;
    if (day <= ovulationEnd) return l10n.cyclePhaseOvulation;
    return l10n.cyclePhaseLuteal;
  }

  Color phaseColor(DateTime date) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return RhythmaColors.rose;
    if (day <= follicularEnd) return RhythmaColors.primary;
    if (day <= ovulationEnd) return RhythmaColors.teal;
    return RhythmaColors.coral;
  }
}
