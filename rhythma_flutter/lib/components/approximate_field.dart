import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../config/theme.dart';

class ApproxRange {
  
  final String key;

  final String label;

  final double midpoint;

  const ApproxRange({
    required this.key,
    required this.label,
    required this.midpoint,
  });
}

class ApproximateField extends StatelessWidget {
  
  final String label;

  final String hint;

  final String unit;

  final List<ApproxRange> ranges;

  final TextEditingController controller;

  final bool isEstimated;

  final ValueChanged<bool> onEstimatedChanged;

  final String? selectedRange;

  final ValueChanged<String> onRangeChanged;

  final String? error;

  final bool isDecimal;

  final double minValue;

  final double maxValue;

  final String toggleLabel;

  final String approximateLabel;

  const ApproximateField({
    super.key,
    required this.label,
    required this.hint,
    required this.unit,
    required this.ranges,
    required this.controller,
    required this.isEstimated,
    required this.onEstimatedChanged,
    this.selectedRange,
    required this.onRangeChanged,
    this.error,
    this.isDecimal = false,
    this.minValue = 0,
    this.maxValue = 999,
    required this.toggleLabel,
    required this.approximateLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        
        Row(
          children: [
            Text(
              label,
              style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg),
            ),
            if (isEstimated) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: RhythmaColors.primary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '($approximateLabel)',
                  style: TextStyle(
                    fontSize: 11,
                    color: RhythmaColors.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 8),

        TextField(
          controller: controller,
          keyboardType: isDecimal
              ? const TextInputType.numberWithOptions(decimal: true)
              : TextInputType.number,
          enabled: !isEstimated,
          inputFormatters: [
            FilteringTextInputFormatter.allow(
              isDecimal ? RegExp(r'[0-9.]') : RegExp(r'[0-9]'),
            ),
          ],
          style: TextStyle(color: RhythmaColors.foreground),
          decoration: InputDecoration(
            hintText: '$hint ($unit)',
            errorText: error,
            labelStyle: TextStyle(color: RhythmaColors.mutedFg),
            hintStyle: TextStyle(
              color: RhythmaColors.mutedFg.withValues(alpha: 0.6),
            ),
            filled: true,
            fillColor: isEstimated
                ? RhythmaColors.surface.withValues(alpha: 0.5)
                : RhythmaColors.surface,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(
                color: RhythmaColors.primary.withValues(alpha: 0.2),
              ),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(
                color: RhythmaColors.primary,
                width: 1.5,
              ),
            ),
            disabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(
                color: RhythmaColors.primary.withValues(alpha: 0.1),
              ),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.redAccent, width: 1.5),
            ),
          ),
        ),
        const SizedBox(height: 8),

        GestureDetector(
          onTap: () => onEstimatedChanged(!isEstimated),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Switch(
                value: isEstimated,
                onChanged: onEstimatedChanged,
                activeThumbColor: RhythmaColors.primary,
                inactiveThumbColor: RhythmaColors.mutedFg,
                activeTrackColor: RhythmaColors.primary.withValues(alpha: 0.3),
                inactiveTrackColor: RhythmaColors.surface,
              ),
              const SizedBox(width: 4),
              Text(
                toggleLabel,
                style: TextStyle(
                  fontSize: 13,
                  color: isEstimated
                      ? RhythmaColors.primary
                      : RhythmaColors.mutedFg,
                  fontWeight: isEstimated ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ],
          ),
        ),

        if (isEstimated) ...[
          const SizedBox(height: 8),
          ...ranges.map((range) {
            final isSelected = selectedRange == range.key;
            return RadioListTile<String>(
              value: range.key,
              groupValue: selectedRange,
              onChanged: (v) {
                if (v != null) onRangeChanged(v);
              },
              title: Text(
                range.label,
                style: TextStyle(
                  fontSize: 14,
                  color: isSelected
                      ? RhythmaColors.primary
                      : RhythmaColors.foreground,
                ),
              ),
              activeColor: RhythmaColors.primary,
              contentPadding: EdgeInsets.zero,
              dense: true,
            );
          }),
        ],
      ],
    );
  }
}
