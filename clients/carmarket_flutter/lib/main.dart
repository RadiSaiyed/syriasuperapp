import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/browse_screen.dart';
import 'screens/my_offers_screen.dart';
import 'screens/my_listings_screen.dart';
import 'screens/favorites_screen.dart';
import 'ui/glass.dart';
import 'package:shared_ui/shared_ui.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

class App extends StatefulWidget {
  const App({super.key});
  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  final _tokenStore = TokenStore();
  late ApiClient _api;
  String _baseUrl = 'http://localhost:8086';
  static const _baseUrlKey = 'carmarket_base_url';
  static const _oldBaseUrlKey = 'automarket_base_url';
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(baseUrl: _baseUrl, tokenStore: _tokenStore);
    _loadBaseUrl();
    _devAutoLoginIfNeeded();
  }

  Future<void> _loadBaseUrl() async {
    final p = await SharedPreferences.getInstance();
    String? saved = p.getString(_baseUrlKey);
    saved ??= p.getString(_oldBaseUrlKey);
    if (saved != null && saved.isNotEmpty) {
      setState(() { _baseUrl = saved!; _api.baseUrl = _baseUrl; });
    }
  }

  Future<void> _updateBaseUrl(String url) async {
    final v = url.trim();
    setState(() { _baseUrl = v; _api.baseUrl = _baseUrl; });
    final p = await SharedPreferences.getInstance();
    await p.setString(_baseUrlKey, v);
  }

  Future<void> _devAutoLoginIfNeeded() async {
    if (kReleaseMode) return;
    final t = await _tokenStore.getToken();
    if (t != null && t.isNotEmpty) return;
    try {
      const phone = '+963900000001';
      await _api.requestOtp(phone);
      await _api.verifyOtp(phone: phone, otp: '123456', name: 'Dev');
      if (mounted) setState(() {});
    } catch (_) {
      // ignore in dev auto login
    }
  }

  @override
  Widget build(BuildContext context) {
    final seed = const Color(0xFF0A84FF);
    return MaterialApp(
      title: 'Car Market',
      themeMode: ThemeMode.dark,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.light),
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: const AppBarTheme(backgroundColor: Colors.transparent, surfaceTintColor: Colors.transparent, elevation: 0, centerTitle: true),
        dialogTheme: DialogThemeData(backgroundColor: Colors.white.withOpacity(0.16), surfaceTintColor: Colors.transparent, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
        bottomSheetTheme: const BottomSheetThemeData(backgroundColor: Colors.transparent, surfaceTintColor: Colors.transparent, elevation: 0),
        cardTheme: CardThemeData(color: Colors.white.withOpacity(0.18), surfaceTintColor: Colors.transparent, elevation: 0, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
        listTileTheme: const ListTileThemeData(textColor: Colors.black87, iconColor: Colors.black87),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white.withOpacity(0.08),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        ),
        pageTransitionsTheme: const PageTransitionsTheme(builders: {
          TargetPlatform.android: CupertinoPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
          TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
        }),
      ),
      darkTheme: SharedTheme.dark(),
      builder: (context, child) => Stack(children: [
        const LiquidBackground(),
        if (child != null) child,
      ]),
      home: FutureBuilder<String?>(
        future: _tokenStore.getToken(),
        builder: (context, snap) {
          final token = snap.data;
          final loggedIn = token != null && token.isNotEmpty;
          return Scaffold(
            extendBody: true,
            extendBodyBehindAppBar: true,
            appBar: AppBar(
              title: const Text('Car Market'),
              flexibleSpace: const Padding(
                padding: EdgeInsets.only(top: 0),
                child: Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero),
              ),
              actions: [
              IconButton(
                icon: const Icon(Icons.account_balance_wallet_outlined),
                tooltip: 'Open Payments',
                onPressed: () async {
                  final uri = Uri.parse('payments://');
                  if (await canLaunchUrl(uri)) {
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  } else {
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed.')));
                  }
                },
              ),
              IconButton(
                icon: const Icon(Icons.settings_ethernet),
                tooltip: 'Set Base URL',
                onPressed: () async {
                  final ctrl = TextEditingController(text: _baseUrl);
                  final url = await showDialog<String>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: const Text('Set Base URL'),
                      content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'http://localhost:8086')),
                      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save'))],
                    ),
                  );
                  if (url != null && url.isNotEmpty) await _updateBaseUrl(url);
                },
              )
            ]),
            body: loggedIn
                ? Column(children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(12, 12 + kToolbarHeight, 12, 8),
                      child: Glass(
                        padding: EdgeInsets.zero,
                        child: NavigationBar(
                          selectedIndex: _tab,
                          onDestinationSelected: (i) => setState(() => _tab = i),
                          indicatorColor: Theme.of(context).colorScheme.primary.withOpacity(0.20),
                          destinations: const [
                            NavigationDestination(icon: Icon(Icons.directions_car), label: 'Browse'),
                            NavigationDestination(icon: Icon(Icons.favorite), label: 'Favorites'),
                            NavigationDestination(icon: Icon(Icons.local_offer), label: 'My Offers'),
                            NavigationDestination(icon: Icon(Icons.garage), label: 'My Listings'),
                          ],
                        ),
                      ),
                    ),
                    Expanded(
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 280),
                        switchInCurve: Curves.easeOutCubic,
                        switchOutCurve: Curves.easeInCubic,
                        child: _tab == 0
                            ? BrowseScreen(key: const ValueKey('tab_browse'), api: _api)
                            : _tab == 1
                                ? FavoritesScreen(key: const ValueKey('tab_fav'), api: _api)
                                : _tab == 2
                                    ? MyOffersScreen(key: const ValueKey('tab_offers'), api: _api)
                                    : MyListingsScreen(key: const ValueKey('tab_listings'), api: _api),
                      ),
                    ),
                  ])
                : Padding(
                    padding: const EdgeInsets.only(top: kToolbarHeight + 12),
                    child: LoginScreen(api: _api, onLoggedIn: () => setState(() {})),
                  ),
          );
        },
      ),
    );
  }
}
