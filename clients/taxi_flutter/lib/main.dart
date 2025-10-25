import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'screens/rider_screen.dart';
import 'l10n/app_localizations.dart';
import 'package:shared_ui/shared_ui.dart';
import 'package:shared_ui/glass.dart';
import 'push.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'screens/history_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await dotenv.load(fileName: ".env");
  } catch (_) {}
  runApp(const App());
}

class _DefaultLoginPlaceholder extends StatelessWidget {
  final Future<void> Function()? onRefresh;
  const _DefaultLoginPlaceholder({this.onRefresh});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Card(
          color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.30),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.lock_outline, size: 48),
                const SizedBox(height: 16),
                const Text(
                  'Taxi requires an authenticated session.\nSign in via the SuperApp profile (Payments login) and return here.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: onRefresh == null ? null : () => onRefresh!.call(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Check again'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class App extends StatefulWidget {
  final String? initialBaseUrl;
  final TokenStore? tokenStore;
  final WidgetBuilder? loginPlaceholderBuilder;
  const App(
      {super.key,
      this.initialBaseUrl,
      this.tokenStore,
      this.loginPlaceholderBuilder});

  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> with WidgetsBindingObserver {
  late final TokenStore _tokenStore;
  late ApiClient _api;
  late String _baseUrl;
  // Rider‑only app (Driver UI ist ausgelagert in taxi_driver_flutter)
  PushManager? _push;
  bool _pushInitialized = false;
  bool _sessionLoading = true;
  bool _hasToken = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _tokenStore = widget.tokenStore ?? TokenStore();
    _baseUrl = widget.initialBaseUrl ?? 'http://localhost:8092';
    _api = ApiClient(baseUrl: _baseUrl, tokenStore: _tokenStore);
    _reloadSession();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _disposePush();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _reloadSession();
    }
  }

  Future<void> _reloadSession() async {
    final token = await _tokenStore.getToken();
    final hasToken = token != null && token.isNotEmpty;
    if (!mounted) return;
    setState(() {
      _hasToken = hasToken;
      _sessionLoading = false;
    });
    if (hasToken) {
      await _ensurePushInitialized();
    } else {
      _disposePush();
    }
  }

  Future<void> _ensurePushInitialized() async {
    if (_pushInitialized) return;
    try {
      _push ??= PushManager(api: _api, appMode: 'rider');
      await _push!.init();
      _pushInitialized = true;
    } catch (e) {
      debugPrint('Push init failed: $e');
    }
  }

  void _disposePush() {
    _pushInitialized = false;
    _push = null;
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      onGenerateTitle: (ctx) {
        final loc = AppLocalizations.of(ctx);
        return loc?.appTitleRider ?? 'Taxi Rider';
      },
      themeMode: ThemeMode.dark,
      theme: SharedTheme.dark().copyWith(
        // transparent to reveal Liquid background like Super‑App
        scaffoldBackgroundColor: Colors.transparent,
        pageTransitionsTheme: const PageTransitionsTheme(builders: {
          TargetPlatform.android: CupertinoPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
          TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
        }),
      ),
      darkTheme: SharedTheme.dark().copyWith(
        scaffoldBackgroundColor: Colors.transparent,
        pageTransitionsTheme: const PageTransitionsTheme(builders: {
          TargetPlatform.android: CupertinoPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
          TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
        }),
      ),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      builder: (context, child) => Stack(children: [
        const LiquidBackground(),
        const LiquidGlassOverlay(opacity: 0.30, blur: 60),
        if (child != null) child,
      ]),
      home: Builder(
        builder: (context) {
          final loc = AppLocalizations.of(context)!;
          final String title = loc.appTitleRider;
          final WidgetBuilder placeholderBuilder =
              widget.loginPlaceholderBuilder ??
                  (ctx) => _DefaultLoginPlaceholder(
                        onRefresh: _reloadSession,
                      );
          Widget body;
          if (_sessionLoading) {
            body = const Center(child: CircularProgressIndicator());
          } else if (_hasToken) {
            body = RiderScreen(api: _api);
          } else {
            body = placeholderBuilder(context);
          }
          final bool loggedIn = _hasToken && !_sessionLoading;

          return Scaffold(
            appBar: AppBar(
                leading: Builder(
                  builder: (context) {
                    final innerNav = Navigator.of(context);
                    final rootNav = Navigator.of(context, rootNavigator: true);
                    final bool canPopInner = innerNav.canPop();
                    final bool canPopRoot = rootNav.canPop();
                    if (!canPopInner && !canPopRoot) {
                      return const SizedBox.shrink();
                    }
                    return IconButton(
                      tooltip: 'Back',
                      icon: const Icon(Icons.arrow_back_ios_new),
                      onPressed: () {
                        if (innerNav.canPop()) {
                          innerNav.pop();
                        } else if (rootNav.canPop()) {
                          rootNav.pop();
                        }
                      },
                    );
                  },
                ),
                title: Text(title),
                actions: [
                  IconButton(
                    tooltip: 'Ride history',
                    icon: const Icon(Icons.history),
                    onPressed: loggedIn
                        ? () {
                            Navigator.of(context).push(MaterialPageRoute(
                                builder: (_) => HistoryScreen(api: _api)));
                          }
                        : null,
                  ),
                  IconButton(
                    icon: const Icon(Icons.account_balance_wallet_outlined),
                    tooltip: loc.openPayments,
                    onPressed: () async {
                      final uri = Uri.parse('payments://');
                      if (await canLaunchUrl(uri)) {
                        await launchUrl(uri,
                            mode: LaunchMode.externalApplication);
                      } else {
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('Payments app not installed.')));
                      }
                    },
                  ),
                  IconButton(
                    icon: const Icon(Icons.settings_ethernet),
                    onPressed: () async {
                      final ctrl = TextEditingController(text: _baseUrl);
                      final url = await showDialog<String>(
                        context: context,
                        builder: (_) => AlertDialog(
                          title: Text(loc.setBaseUrl),
                          content: TextField(
                              controller: ctrl,
                              decoration: const InputDecoration(
                                  hintText: 'http://localhost:8092')),
                          actions: [
                            TextButton(
                                onPressed: () => Navigator.pop(context),
                                child: Text(loc.cancel)),
                            FilledButton(
                                onPressed: () =>
                                    Navigator.pop(context, ctrl.text),
                                child: Text(loc.save))
                          ],
                        ),
                      );
                      if (url != null && url.isNotEmpty) {
                        setState(() {
                          _baseUrl = url.trim();
                          _api.baseUrl = _baseUrl;
                        });
                        _disposePush();
                        _reloadSession();
                      }
                    },
                  )
                ]),
            body: body,
            bottomNavigationBar: null,
          );
        },
      ),
    );
  }
}
