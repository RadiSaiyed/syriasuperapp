import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'l10n/app_localizations.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/driver_screen.dart';
import 'push.dart';
import 'package:shared_ui/shared_ui.dart';
import 'package:shared_ui/glass.dart';
import 'push.dart' as push_bg;
import 'package:firebase_messaging/firebase_messaging.dart';
import 'ui/notify.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:convert';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await dotenv.load(fileName: ".env");
  } catch (_) {}
  // Ensure background FCM handler is registered early
  try {
    FirebaseMessaging.onBackgroundMessage(push_bg.firebaseMessagingBackgroundHandler);
  } catch (_) {}
  runApp(const DriverApp());
}

class DriverApp extends StatefulWidget {
  const DriverApp({super.key});
  @override
  State<DriverApp> createState() => _DriverAppState();
}

class _DriverAppState extends State<DriverApp> {
  final _tokenStore = TokenStore();
  late ApiClient _api;
  String _baseUrl = 'http://localhost:8092';
  PushManager? _push;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(baseUrl: _baseUrl, tokenStore: _tokenStore);
    // Configure local notification action handler (e.g., Accept ride)
    Notify.init(onAction: (String actionId, String? payload) async {
      try {
        if (actionId == 'ACCEPT_RIDE' && payload != null) {
          final js = jsonDecode(payload) as Map<String, dynamic>;
          final rideId = js['ride_id'] as String?;
          if (rideId != null && rideId.isNotEmpty) {
            await _api.rideAccept(rideId);
          }
        }
      } catch (_) {}
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Taxi Driver',
      themeMode: ThemeMode.dark,
      theme: SharedTheme.dark().copyWith(
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
      supportedLocales: const [Locale('en'), Locale('ar')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        AppLocalizations.delegate,
      ],
      builder: (context, child) => Stack(children: [
        const LiquidBackground(),
        const LiquidGlassOverlay(opacity: 0.24, blur: 48),
        if (child != null) child,
      ]),
      home: FutureBuilder<String?>(
        future: _tokenStore.getToken(),
        builder: (context, snap) {
          final token = snap.data;
          final loggedIn = token != null && token.isNotEmpty;
          final body = loggedIn
              ? DriverScreen(api: _api)
              : LoginScreen(
                  api: _api,
                  onLoggedIn: () async {
                    setState(() {});
                    try {
                      _push = PushManager(api: _api, appMode: 'driver');
                      await _push!.init();
                    } catch (_) {}
                  },
                );
          final loc = AppLocalizations.of(context);
          final title = loc?.appTitleDriver ?? 'Taxi Driver';
          return Scaffold(
            appBar: AppBar(title: Text(title), actions: [
              IconButton(
                icon: const Icon(Icons.account_balance_wallet_outlined),
                tooltip: loc?.openPayments ?? 'Open Payments',
                onPressed: () async {
                  final uri = Uri.parse('payments://');
                  if (await canLaunchUrl(uri)) {
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  } else {
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
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
                      title: Text(loc?.setBaseUrl ?? 'Set Base URL'),
                      content: TextField(
                          controller: ctrl,
                          decoration: const InputDecoration(
                              hintText: 'http://localhost:8092')),
                      actions: [
                        TextButton(
                            onPressed: () => Navigator.pop(context),
                            child: Text(loc?.cancel ?? 'Cancel')),
                        FilledButton(
                            onPressed: () => Navigator.pop(context, ctrl.text),
                            child: Text(loc?.save ?? 'Save'))
                      ],
                    ),
                  );
                  if (url != null && url.isNotEmpty) {
                    setState(() {
                      _baseUrl = url.trim();
                      _api.baseUrl = _baseUrl;
                      if (_push != null) {
                        _push = PushManager(api: _api, appMode: 'driver');
                        _push!.init();
                      }
                    });
                  }
                },
              )
            ]),
            body: body,
          );
        },
      ),
    );
  }
}
