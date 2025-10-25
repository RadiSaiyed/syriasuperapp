library shared_ui;

import 'package:flutter/material.dart';

class SharedColors {
  static const background = Color(0xFF0A0A0A);
  static const surface = Color(0xFF1A1A1A);
  static const surfaceVariant = Color(0xFF121212);
  static const outline = Color(0xFF2E2E2E);

  static const textPrimary = Color(0xFFFFFFFF);
  static const textSecondary = Color(0xFFB3B3B3);

  static const lime = Color(0xFFA4FF00);
  static const orange = Color(0xFFFF7A00);
  static const blue = Color(0xFF00BFFF);
  static const pink = Color(0xFFFF3CAC);
  static const red = Color(0xFFFF4040);
}

class CategoryColors {
  static const payments = SharedColors.lime;
  static const freight = SharedColors.lime;
  static const taxi = SharedColors.blue;
  static const flights = SharedColors.blue;
  static const jobs = SharedColors.blue;
  static const doctors = SharedColors.blue;
  static const food = SharedColors.pink;
  static const stays = SharedColors.pink;
  static const chat = SharedColors.pink;
  static const commerce = SharedColors.orange;
  static const utilities = SharedColors.orange;
  static const realestate = SharedColors.orange;
  static const carmarket = SharedColors.orange;
}

class SharedTheme {
  static ThemeData dark() {
    final cs = ColorScheme(
      brightness: Brightness.dark,
      primary: SharedColors.lime,
      onPrimary: Colors.black,
      secondary: SharedColors.blue,
      onSecondary: Colors.black,
      error: SharedColors.red,
      onError: Colors.black,
      surface: SharedColors.surface,
      onSurface: SharedColors.textPrimary,
      tertiary: SharedColors.pink,
      onTertiary: Colors.black,
      surfaceVariant: SharedColors.surfaceVariant,
      onSurfaceVariant: SharedColors.textSecondary,
      outline: SharedColors.outline,
      outlineVariant: SharedColors.outline,
      shadow: Colors.black,
      scrim: Colors.black,
      inverseSurface: const Color(0xFF0F0F0F),
      onInverseSurface: SharedColors.textPrimary,
      inversePrimary: SharedColors.blue,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: cs,
      scaffoldBackgroundColor: SharedColors.background,
      appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          centerTitle: true,
          foregroundColor: SharedColors.textPrimary),
      dialogTheme: DialogThemeData(
          backgroundColor: SharedColors.surface,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
      cardTheme: CardThemeData(
          color: SharedColors.surface,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: SharedColors.surfaceVariant,
        border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: SharedColors.outline)),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: SharedColors.outline)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: SharedColors.lime, width: 2)),
        hintStyle: const TextStyle(color: SharedColors.textSecondary),
        labelStyle: const TextStyle(color: SharedColors.textSecondary),
      ),
      textTheme: const TextTheme(
        bodyMedium: TextStyle(color: SharedColors.textPrimary),
        bodySmall: TextStyle(color: SharedColors.textSecondary),
        titleMedium:
            TextStyle(color: SharedColors.textPrimary, fontWeight: FontWeight.w600),
      ),
      iconTheme: const IconThemeData(color: SharedColors.textPrimary),
      listTileTheme: const ListTileThemeData(
          textColor: SharedColors.textPrimary,
          iconColor: SharedColors.textSecondary),
      bottomSheetTheme: const BottomSheetThemeData(
          backgroundColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          elevation: 0),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: SharedColors.lime,
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          side: const BorderSide(color: SharedColors.lime),
          foregroundColor: SharedColors.lime,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: Colors.transparent,
        indicatorColor: Color(0x33A4FF00),
        labelTextStyle:
            WidgetStatePropertyAll(TextStyle(color: SharedColors.textSecondary)),
        iconTheme:
            WidgetStatePropertyAll(IconThemeData(color: SharedColors.textPrimary)),
      ),
      dividerTheme:
          const DividerThemeData(color: SharedColors.outline, space: 1),
      chipTheme: const ChipThemeData(
        backgroundColor: SharedColors.surfaceVariant,
        labelStyle: TextStyle(color: SharedColors.textPrimary),
        side: BorderSide(color: SharedColors.outline),
      ),
    );
  }
}

