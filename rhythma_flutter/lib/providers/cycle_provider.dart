import 'package:flutter/material.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

class CycleProvider extends ChangeNotifier {
  DateTime get _today => DateTime.now();

  late DateTime _selectedDate;
  late DateTime _displayedMonth;

  CycleProvider() {
    final today = _today;
    _selectedDate = DateTime(today.year, today.month, today.day);
    _displayedMonth = DateTime(today.year, today.month);
  }

  DateTime get selectedDate => _selectedDate;
  DateTime get displayedMonth => _displayedMonth;

  void selectDate(DateTime date) {
    final today = DateTime(_today.year, _today.month, _today.day);
    final normalized = DateTime(date.year, date.month, date.day);
    if (normalized.isAfter(today)) return; // no logging for future days
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

  /// Whether anything has actually been saved for [date] (Home quick-log
  /// tiles or the Cycle screen's log rows/Save button both write through
  /// LocalStorageService, so this always reflects real data — not a mock).
  bool hasLogsForDate(DateTime date) {
    return LocalStorageService.getCycleLogForDate(date) != null;
  }

  /// Notifies listeners (e.g. to redraw the calendar's "logged" dot) after
  /// a log write elsewhere. The log itself is persisted by whoever calls
  /// this — this provider intentionally doesn't hold log data itself, just
  /// the calendar's navigation/selection state.
  void refresh() => notifyListeners();

  void refreshLogs() {
    notifyListeners();
  }

  // ── Cycle-length settings ────────────────────────────────────────────
  // Read fresh from the profile each time (rather than cached at
  // construction) so edits made on the Profile/Onboarding screens are
  // reflected immediately without having to recreate the provider.

  int get _periodDuration {
    final profile = LocalStorageService.getProfile();
    return (profile?['period_duration'] as num?)?.toInt() ?? 5;
  }

  int get _cycleLength {
    final profile = LocalStorageService.getProfile();
    return (profile?['cycle_length'] as num?)?.toInt() ?? 28;
  }

  /// Day-of-cycle for [date], counted from the saved `last_period` start
  /// date (1-indexed, wraps across multiple cycle lengths). Falls back to
  /// the plain day-of-month when no `last_period` has been saved yet.
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

    // Modulo that stays positive even if `date` falls before `last_period`.
    final cycleDay = ((daysSince % cycleLength) + cycleLength) % cycleLength;
    return cycleDay + 1;
  }

  /// Returns 0 (menstrual), 1 (follicular), 2 (ovulation), or 3 (luteal).
  int _phaseIndex(DateTime date) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return 0;
    if (day <= follicularEnd) return 1;
    if (day <= ovulationEnd) return 2;
    return 3;
  }

  String phaseKey(DateTime date) {
    return const ['menstrual', 'follicular', 'ovulation', 'luteal']
        [_phaseIndex(date)];
  }

  String phase(DateTime date, AppLocalizations l10n) {
    return [
      l10n.cyclePhasePeriod,
      l10n.cyclePhaseFollicular,
      l10n.cyclePhaseOvulation,
      l10n.cyclePhaseLuteal,
    ][_phaseIndex(date)];
  }

  Color phaseColor(DateTime date) {
    return const [
      RhythmaColors.rose,
      RhythmaColors.primary,
      RhythmaColors.teal,
      RhythmaColors.coral,
    ][_phaseIndex(date)];
  }
}
