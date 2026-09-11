import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../../components/shared.dart';
import '../../../config/theme.dart';
import '../../../models/cycle_log.dart';
import '../../../services/cycle_service.dart';
import '../../../providers/cycle_provider.dart';
import '../../../services/local_storage_service.dart';
import '../../../utils/date_utils.dart';
import '../../../utils/log_options.dart';

class LogEntrySheet extends StatefulWidget {
  final DateTime date;
  final Map<String, dynamic>? existingLog;

  const LogEntrySheet({
    super.key,
    required this.date,
    this.existingLog,
  });

  static Future<void> show(BuildContext context, DateTime date,
      {Map<String, dynamic>? existingLog}) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      builder: (context) => LogEntrySheet(date: date, existingLog: existingLog),
    );
  }

  @override
  State<LogEntrySheet> createState() => _LogEntrySheetState();
}

class _LogEntrySheetState extends State<LogEntrySheet> {
  String? _flowIntensity;
  String? _mood;
  double _sleepHours = 8.0;
  double _stressLevel = 1.0;
  List<String> _symptoms = [];

  final List<Map<String, dynamic>> _moodOptions = [
    {'emoji': '😊', 'label': 'Happy', 'color': RhythmaColors.teal},
    {'emoji': '😌', 'label': 'Calm', 'color': Color(0xFF7BAFD4)},
    {'emoji': '😐', 'label': 'Neutral', 'color': RhythmaColors.mutedFg},
    {'emoji': '😔', 'label': 'Low', 'color': RhythmaColors.rose},
    {'emoji': '😢', 'label': 'Sad', 'color': RhythmaColors.coral},
    {'emoji': '😤', 'label': 'Irritated', 'color': Color(0xFFE8905B)},
  ];

  @override
  void initState() {
    super.initState();
    if (widget.existingLog != null) {
      final log = widget.existingLog!;
      _flowIntensity = log['flow_intensity'] as String?;
      _mood = log['mood'] as String?;
      _sleepHours = ((log['sleep_hours'] as num?)?.toDouble() ?? 8.0).clamp(0.0, 16.0);
      _stressLevel = (log['stress_level'] as num?)?.toDouble() ?? 1.0;
      if (log['symptoms'] != null) {
        _symptoms = List<String>.from(log['symptoms'] as List);
      }
    }
  }

  Future<void> _saveLog() async {
    final log = {
      if (widget.existingLog != null) ...widget.existingLog!,
      'start_date': RhythmaDateUtils.toDateKey(widget.date),
      if (_flowIntensity != null) 'flow_intensity': _flowIntensity,
      if (_mood != null) 'mood': _mood,
      'sleep_hours': _sleepHours,
      'stress_level': _stressLevel,
      'symptoms': _symptoms,
    };
    await LocalStorageService.saveCycleLog(log);

    try {
      await CycleService().submitLog(
        CycleLog(
          startDate: widget.date,
          flowIntensity: log['flow_intensity'] as String?,
          mood: log['mood'] as String?,
          sleepHours: (log['sleep_hours'] as num?)?.toDouble(),
          stressLevel: (log['stress_level'] as num?)?.toInt(),
          symptoms: List<String>.from(log['symptoms'] as List? ?? []),
        ),
      );
    } catch (_) {}

    if (mounted) {
      context.read<CycleProvider>().refresh();
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.logSaved),
          behavior: SnackBarBehavior.floating,
          backgroundColor: RhythmaColors.teal,
        ),
      );
      Navigator.of(context).pop();
    }
  }

  Future<void> _deleteLog() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: RhythmaColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Delete Entry'),
        content: const Text(
          'Are you sure you want to delete this day\'s log? This cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final dateKey = RhythmaDateUtils.toDateKey(widget.date);
    await LocalStorageService.deleteCycleLog(dateKey);

    if (mounted) {
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.logDeleted),
          behavior: SnackBarBehavior.floating,
        ),
      );
      Navigator.of(context).pop();
    }

    try {
      await CycleService().deleteLog(dateKey);
    } catch (_) {}

    if (!mounted) return;
    context.read<CycleProvider>().refresh();
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return DraggableScrollableSheet(
      initialChildSize: 0.92,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: RhythmaColors.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          ),
          child: Column(
            children: [
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(top: 12),
                decoration: BoxDecoration(
                  color: RhythmaColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      widget.existingLog != null ? 'Update Log' : l10n.logTitle,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: RhythmaColors.foreground,
                      ),
                    ),
                    Row(
                      children: [
                        if (widget.existingLog != null)
                          IconButton(
                            icon: const Icon(Icons.delete_outline_rounded, size: 20),
                            color: RhythmaColors.coral,
                            onPressed: _deleteLog,
                          ),
                        IconButton(
                          icon: const Icon(Icons.close, size: 20),
                          color: RhythmaColors.mutedFg,
                          onPressed: () => Navigator.of(context).pop(),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
                  children: [
                    _buildSection(
                      icon: Icons.water_drop_rounded,
                      label: l10n.logFlowIntensity,
                      color: RhythmaColors.rose,
                      child: _buildFlowPicker(l10n),
                    ),
                    const SizedBox(height: 16),
                    _buildSection(
                      icon: Icons.emoji_emotions_rounded,
                      label: l10n.logMood,
                      color: RhythmaColors.teal,
                      child: _buildMoodPicker(),
                    ),
                    const SizedBox(height: 16),
                    _buildSection(
                      icon: Icons.bedtime_rounded,
                      label: '${l10n.logSleepHours}: ${_sleepHours.toInt()}h',
                      color: Color(0xFF7BAFD4),
                      child: _buildSlider(
                        value: _sleepHours.clamp(0.0, 16.0),
                        min: 0,
                        max: 16,
                        divisions: 16,
                        label: '${_sleepHours.toInt()}h',
                        gradient: const LinearGradient(
                          colors: [Color(0xFF7BAFD4), Color(0xFF3B6B8E)],
                        ),
                        onChanged: (v) => setState(() => _sleepHours = v),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildSection(
                      icon: Icons.psychology_rounded,
                      label: '${l10n.logStressLevel}: ${_stressLevel.toInt()}/5',
                      color: RhythmaColors.coral,
                      child: _buildSlider(
                        value: _stressLevel,
                        min: 1,
                        max: 5,
                        divisions: 4,
                        label: '${_stressLevel.toInt()}',
                        gradient: const LinearGradient(
                          colors: [RhythmaColors.coral, Color(0xFFE8905B)],
                        ),
                        onChanged: (v) => setState(() => _stressLevel = v),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildSection(
                      icon: Icons.healing_rounded,
                      label: l10n.logLabelSymptoms,
                      color: RhythmaColors.primary,
                      child: _buildSymptomPicker(l10n),
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: RhythmaGradients.primary,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: ElevatedButton(
                    onPressed: _saveLog,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    child: Text(
                      l10n.logSave,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSection({
    required IconData icon,
    required String label,
    required Color color,
    required Widget child,
  }) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              TintedIcon(icon: icon, color: color, size: 32),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: RhythmaColors.foreground,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }

  Widget _buildFlowPicker(AppLocalizations l10n) {
    final options = [
      {'value': 'spotting', 'label': l10n.logFlowSpotting, 'icon': Icons.circle, 'size': 8.0, 'color': RhythmaColors.rose},
      {'value': 'light', 'label': l10n.logLight, 'icon': Icons.circle, 'size': 12.0, 'color': RhythmaColors.coral},
      {'value': 'medium', 'label': l10n.logMedium, 'icon': Icons.circle, 'size': 16.0, 'color': RhythmaColors.primary},
      {'value': 'heavy', 'label': l10n.logHeavy, 'icon': Icons.circle, 'size': 20.0, 'color': RhythmaColors.teal},
    ];

    return Row(
      children: options.map((opt) {
        final isSelected = _flowIntensity == opt['value'];
        return Expanded(
          child: GestureDetector(
            onTap: () => setState(() {
              _flowIntensity = isSelected ? null : opt['value'] as String;
            }),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.symmetric(horizontal: 3),
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                gradient: isSelected ? RhythmaGradients.primary : null,
                color: isSelected ? null : RhythmaColors.surfaceMuted,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isSelected
                      ? RhythmaColors.primary
                      : RhythmaColors.border,
                  width: isSelected ? 1.5 : 1,
                ),
              ),
              child: Column(
                children: [
                  Icon(
                    opt['icon'] as IconData,
                    size: opt['size'] as double,
                    color: isSelected ? Colors.white : (opt['color'] as Color),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    opt['label'] as String,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      color: isSelected ? Colors.white : RhythmaColors.mutedFg,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildMoodPicker() {
    return SizedBox(
      height: 72,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _moodOptions.length,
        itemBuilder: (context, index) {
          final option = _moodOptions[index];
          final isSelected = _mood == option['emoji'];
          final color = option['color'] as Color;

          return GestureDetector(
            onTap: () => setState(() {
              _mood = isSelected ? null : option['emoji'] as String;
            }),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(right: 10),
              width: 64,
              decoration: BoxDecoration(
                gradient: isSelected
                    ? LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          color.withValues(alpha: 0.3),
                          color.withValues(alpha: 0.15),
                        ],
                      )
                    : null,
                color: isSelected ? null : RhythmaColors.surfaceMuted,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected ? color : RhythmaColors.border,
                  width: isSelected ? 1.5 : 1,
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    option['emoji'] as String,
                    style: TextStyle(fontSize: isSelected ? 28 : 24),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    option['label'] as String,
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                      color: isSelected ? color : RhythmaColors.mutedFg,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildSlider({
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String label,
    required LinearGradient gradient,
    required ValueChanged<double> onChanged,
  }) {
    final fraction = (value - min) / (max - min);
    return Column(
      children: [
        SliderTheme(
          data: SliderThemeData(
            trackHeight: 6,
            activeTrackColor: Colors.transparent,
            inactiveTrackColor: RhythmaColors.surfaceMuted,
            overlayShape: const RoundSliderOverlayShape(overlayRadius: 16),
            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
            thumbColor: Colors.white,
            overlayColor: RhythmaColors.primary.withValues(alpha: 0.15),
          ),
          child: Stack(
            children: [
              Slider(
                value: value,
                min: min,
                max: max,
                divisions: divisions,
                label: label,
                onChanged: onChanged,
              ),
              Positioned.fill(
                child: IgnorePointer(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: FractionallySizedBox(
                      widthFactor: fraction.clamp(0.0, 1.0),
                      child: Container(
                        decoration: BoxDecoration(
                          gradient: gradient,
                          borderRadius: BorderRadius.circular(3),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                min.toInt().toString(),
                style: TextStyle(fontSize: 10, color: RhythmaColors.mutedFg),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  gradient: gradient,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
              Text(
                max.toInt().toString(),
                style: TextStyle(fontSize: 10, color: RhythmaColors.mutedFg),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSymptomPicker(AppLocalizations l10n) {
    final symptoms = [
      {'id': 'Cramps', 'label': l10n.logSympCramps, 'icon': Icons.fiber_manual_record_rounded},
      {'id': 'Headache', 'label': l10n.logSympHeadache, 'icon': Icons.psychology_rounded},
      {'id': 'Bloating', 'label': l10n.logSympBloating, 'icon': Icons.water_rounded},
      {'id': 'Fatigue', 'label': l10n.logSympFatigue, 'icon': Icons.battery_2_bar_rounded},
      {'id': 'Nausea', 'label': l10n.logSympNausea, 'icon': Icons.sick_rounded},
      {'id': 'Acne', 'label': l10n.logSympAcne, 'icon': Icons.face_rounded},
      {'id': 'Back Pain', 'label': l10n.logSympBackPain, 'icon': Icons.accessibility_new_rounded},
      {'id': 'severe pain', 'label': l10n.logSympSeverePain, 'icon': Icons.warning_amber_rounded},
      {'id': 'fainting', 'label': l10n.logSympFainting, 'icon': Icons.air_rounded},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Healthy (none) option
        GestureDetector(
          onTap: () => setState(() {
            if (_symptoms.contains('healthy_none')) {
              _symptoms.remove('healthy_none');
            } else {
              _symptoms
                ..clear()
                ..add('healthy_none');
            }
          }),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              gradient: _symptoms.contains('healthy_none')
                  ? LinearGradient(
                      colors: [
                        RhythmaColors.teal.withValues(alpha: 0.25),
                        RhythmaColors.teal.withValues(alpha: 0.15),
                      ],
                    )
                  : null,
              color: _symptoms.contains('healthy_none') ? null : RhythmaColors.surfaceMuted,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _symptoms.contains('healthy_none') ? RhythmaColors.teal : RhythmaColors.border,
                width: _symptoms.contains('healthy_none') ? 1.5 : 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.favorite_rounded,
                  size: 14,
                  color: _symptoms.contains('healthy_none') ? RhythmaColors.teal : RhythmaColors.mutedFg,
                ),
                const SizedBox(width: 6),
                Text(
                  l10n.logSympHealthy,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: _symptoms.contains('healthy_none') ? FontWeight.w600 : FontWeight.w400,
                    color: _symptoms.contains('healthy_none') ? RhythmaColors.teal : RhythmaColors.mutedFg,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        // Other symptoms
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: symptoms.map((s) {
            final isSelected = _symptoms.contains(s['id']);
            return GestureDetector(
              onTap: () => setState(() {
                // Clear 'healthy_none' if any other symptom is selected
                if (_symptoms.contains('healthy_none')) {
                  _symptoms.remove('healthy_none');
                }
                if (isSelected) {
                  _symptoms.remove(s['id'] as String);
                } else {
                  _symptoms.add(s['id'] as String);
                }
              }),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  gradient: isSelected
                      ? LinearGradient(
                          colors: [
                            RhythmaColors.primary.withValues(alpha: 0.25),
                            RhythmaColors.primary.withValues(alpha: 0.15),
                          ],
                        )
                      : null,
                  color: isSelected ? null : RhythmaColors.surfaceMuted,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? RhythmaColors.primary : RhythmaColors.border,
                    width: isSelected ? 1.5 : 1,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      s['icon'] as IconData,
                      size: 14,
                      color: isSelected ? RhythmaColors.primary : RhythmaColors.mutedFg,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      s['label'] as String,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                        color: isSelected ? RhythmaColors.primary : RhythmaColors.mutedFg,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }
}
