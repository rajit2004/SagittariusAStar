import 'dart:ui';
import 'package:flutter/material.dart';
import '../config/theme.dart';

class ShellBackground extends StatelessWidget {
  final Widget child;
  final bool showBackButton;
  const ShellBackground(
      {super.key, required this.child, this.showBackButton = true});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBody: true,
        appBar: showBackButton
            ? AppBar(
                backgroundColor: Colors.transparent,
                elevation: 0,
                leading: BackButton(color: RhythmaColors.foreground),
              )
            : null,
        body: SafeArea(top: !showBackButton, child: child),
      ),
    );
  }
}

class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double? borderRadius;
  final VoidCallback? onTap;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.borderRadius,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final r = borderRadius ?? 20.0;
    final card = ClipRRect(
      borderRadius: BorderRadius.circular(r),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 28, sigmaY: 28),
        child: Container(
          decoration: BoxDecoration(
            color: RhythmaColors.surface.withValues(alpha: 0.55),
            borderRadius: BorderRadius.circular(r),
            border: Border.all(
              color: RhythmaColors.lavender.withValues(alpha: 0.28),
              width: 0.8,
            ),
            boxShadow: [
              BoxShadow(
                color: RhythmaColors.primary.withValues(alpha: 0.05),
                blurRadius: 28,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          padding: padding,
          child: Material(
            color: Colors.transparent,
            child: child,
          ),
        ),
      ),
    );
    if (onTap != null) {
      return GestureDetector(onTap: onTap, child: card);
    }
    return card;
  }
}

class GradientBox extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final List<Color>? colors;

  const GradientBox({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.borderRadius = 24,
    this.colors,
  });

   @override
Widget build(BuildContext context) {
  final isDark = Theme.of(context).brightness == Brightness.dark;
  final primaryColor = colors?.first ?? RhythmaColors.primary;

  return Container(
    padding: padding,
    decoration: BoxDecoration(
      gradient: isDark
          ? null
          : LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: colors ??
                  [
                    RhythmaColors.primary,
                    RhythmaColors.primary.withValues(alpha: 0.6),
                  ],
            ),
      color: isDark
          ? primaryColor.withValues(alpha: 0.15)
          : null,
      border: isDark
          ? Border.all(
              color: primaryColor.withValues(alpha: 0.3),
            )
          : null,
      borderRadius: BorderRadius.circular(borderRadius),
      boxShadow: isDark
          ? null
          : [
              BoxShadow(
                color: primaryColor.withValues(alpha: 0.28),
                blurRadius: 40,
                offset: const Offset(0, 10),
              ),
            ],
    ),
    child: child,
  );
}
}

class TintedIcon extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;

  const TintedIcon({
    super.key,
    required this.icon,
    required this.color,
    this.size = 36,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(size * 0.35),
      ),
      child: Icon(icon, color: color, size: size * 0.5),
    );
  }
}

class SectionHeader extends StatelessWidget {
  final String title;
  final String? action;
  final VoidCallback? onAction;

  const SectionHeader({
    super.key,
    required this.title,
    this.action,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12, left: 2, right: 2),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: RhythmaColors.foreground,
              ),
            ),
          ),
          if (action != null)
            GestureDetector(
              onTap: onAction,
              child: Text(
                action!,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: RhythmaColors.primary,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class RhythmaScaffold extends StatelessWidget {
  final Widget body;
  final bool extendBody;

  const RhythmaScaffold({
    super.key,
    required this.body,
    this.extendBody = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        extendBody: extendBody,
        body: body,
      ),
    );
  }
}
