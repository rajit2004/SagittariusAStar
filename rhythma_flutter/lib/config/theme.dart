import 'package:flutter/material.dart';

class RhythmaColors {
  
  static Color primary = const Color(0xFF9B72CF);
  static Color primaryFg = const Color(0xFFFCFAFF);
  static Color lavender = const Color(0xFFD8C8F0);

  static const Color rose = Color(0xFFE07AAD);
  static const Color roseFg = Color(0xFFFCFAFF);

  static const Color teal = Color(0xFF52B3B0);
  static const Color tealFg = Color(0xFFFCFAFF);

  static const Color coral = Color(0xFFE8946A);
  static const Color coralFg = Color(0xFFFCFAFF);

  static Color background = const Color(0xFFFDF8FF);
  static Color backgroundEnd = const Color(0xFFF8EEF8);
  static Color surface = const Color(0xFFFFFFFF);
  static Color surfaceMuted = const Color(0xFFF5F0FA);

  static Color foreground = const Color(0xFF2D1F47);
  static Color mutedFg = const Color(0xFF7A6E8A);

  static Color border = const Color(0xFFE8DFF5);

  static bool isDark = false;

  static Color get glassCard => surface.withValues(alpha: 0.75);
  static Color get glassBorder => lavender.withValues(alpha: 0.4);

  static void updateTheme(bool isDarkMode, Color selectedPrimary) {
    isDark = isDarkMode;
    if (isDarkMode) {
      
      primary = selectedPrimary;
      primaryFg = const Color(0xFFFCFAFF);
      lavender = selectedPrimary.withValues(alpha: 0.3);

      background = const Color(0xFF121212);
      backgroundEnd = const Color(0xFF1E1E1E);
      surface = const Color(0xFF1E1E1E);
      surfaceMuted = const Color(0xFF2C2C2C);
      foreground = const Color(0xFFFDF8FF);
      mutedFg = const Color(0xFFAAA4B0);
      border = const Color(0xFF333333);
    } else {
      
      primary = selectedPrimary;
      primaryFg = selectedPrimary.computeLuminance() > 0.5
          ? const Color(0xFF2D1F47)
          : const Color(0xFFFCFAFF);
      lavender = selectedPrimary.withValues(alpha: 0.3);

background = Color.alphaBlend(
  selectedPrimary.withValues(alpha: 0.04),
  const Color(0xFFFFFFFF),
);

backgroundEnd = Color.alphaBlend(
  selectedPrimary.withValues(alpha: 0.10),
  const Color(0xFFFFFFFF),
);

surface = const Color(0xFFFFFFFF);

surfaceMuted = Color.alphaBlend(
  selectedPrimary.withValues(alpha: 0.07),
  const Color(0xFFFFFFFF),
);

foreground = const Color(0xFF2D1F47);
mutedFg = const Color(0xFF7A6E8A);

border = Color.alphaBlend(
  selectedPrimary.withValues(alpha: 0.15),
  const Color(0xFFFFFFFF),
);
    }
  }
}

class RhythmaGradients {
  static LinearGradient get primary => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [RhythmaColors.primary, RhythmaColors.rose],
      );

  static LinearGradient get bg => LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [RhythmaColors.background, RhythmaColors.backgroundEnd],
      );

  static LinearGradient tinted(Color color) => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          color.withValues(alpha: 0.18),
          color.withValues(alpha: 0.08),
        ],
      );
}

class RhythmaTheme {
  static ThemeData get theme {
    final colorScheme = RhythmaColors.isDark
        ? ColorScheme.dark(
            primary: RhythmaColors.primary,
            secondary: RhythmaColors.teal,
            tertiary: RhythmaColors.rose,
            surface: RhythmaColors.surface,
            onPrimary: RhythmaColors.primaryFg,
            onSecondary: RhythmaColors.tealFg,
            onSurface: RhythmaColors.foreground,
          )
        : ColorScheme.light(
            primary: RhythmaColors.primary,
            secondary: RhythmaColors.teal,
            tertiary: RhythmaColors.rose,
            surface: RhythmaColors.surface,
            onPrimary: RhythmaColors.primaryFg,
            onSecondary: RhythmaColors.tealFg,
            onSurface: RhythmaColors.foreground,
          );

    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Nunito',
      brightness: RhythmaColors.isDark ? Brightness.dark : Brightness.light,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: Colors.transparent,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        iconTheme: IconThemeData(color: RhythmaColors.foreground),
        titleTextStyle: TextStyle(
          color: RhythmaColors.foreground,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          fontFamily: 'Nunito',
        ),
      ),
      textTheme: TextTheme(
        displayLarge: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w700,
          color: RhythmaColors.foreground,
          height: 1.2,
        ),
        titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: RhythmaColors.foreground,
        ),
        titleMedium: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: RhythmaColors.foreground,
        ),
        bodyLarge: TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w400,
          color: RhythmaColors.foreground,
          height: 1.5,
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          color: RhythmaColors.foreground,
          height: 1.4,
        ),
        labelSmall: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: RhythmaColors.mutedFg,
          letterSpacing: 0.8,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: RhythmaColors.primary,
          foregroundColor: RhythmaColors.primaryFg,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: RhythmaColors.surfaceMuted,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: RhythmaColors.primary, width: 1.5),
        ),
        hintStyle: TextStyle(
          color: RhythmaColors.mutedFg,
          fontSize: 14,
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      ),
    );
  }
}
