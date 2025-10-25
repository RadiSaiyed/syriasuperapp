import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import 'api.dart';

class AppModel extends ChangeNotifier {
  final TokenStore tokenStore;
  final Uuid uuid = const Uuid();
  late ApiClient api;
  String baseUrl;
  ThemeMode themeMode;
  static const _baseUrlKey = 'base_url';
  static const _themeKey = 'theme_mode';

  bool loggedIn = false;

  AppModel({required this.tokenStore, required this.baseUrl, this.themeMode = ThemeMode.system}) {
    api = ApiClient(baseUrl: baseUrl, tokenStore: tokenStore);
  }

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    baseUrl = p.getString(_baseUrlKey) ?? baseUrl;
    api.baseUrl = baseUrl;
    final tm = p.getString(_themeKey);
    if (tm != null) {
      themeMode = _parseThemeMode(tm);
    }
    final tok = await tokenStore.getToken();
    loggedIn = tok != null && tok.isNotEmpty;
    notifyListeners();
  }

  Future<void> setBaseUrl(String url) async {
    baseUrl = url.trim();
    api.baseUrl = baseUrl;
    final p = await SharedPreferences.getInstance();
    await p.setString(_baseUrlKey, baseUrl);
    notifyListeners();
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    themeMode = mode;
    final p = await SharedPreferences.getInstance();
    await p.setString(_themeKey, _themeToString(mode));
    notifyListeners();
  }

  void setLoggedIn(bool v) {
    loggedIn = v;
    notifyListeners();
  }

  ThemeMode _parseThemeMode(String s) {
    switch (s) { case 'dark': return ThemeMode.dark; case 'light': return ThemeMode.light; default: return ThemeMode.system; }
  }
  String _themeToString(ThemeMode m) {
    switch (m) { case ThemeMode.dark: return 'dark'; case ThemeMode.light: return 'light'; default: return 'system'; }
  }
}

