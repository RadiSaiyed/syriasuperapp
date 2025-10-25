import 'package:flutter/material.dart';
import 'package:shared_ui/shared_ui.dart';

class AppTheme {
  static ThemeData light({Color seed = const Color(0xFF16A34A)}) => ThemeData(
        colorSchemeSeed: seed,
        useMaterial3: true,
        brightness: Brightness.light,
      );
  static ThemeData dark({Color seed = const Color(0xFF16A34A)}) => SharedTheme.dark();
}
