import 'package:flutter/material.dart';
import 'dart:async';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:uni_links/uni_links.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'package:flutter_windowmanager/flutter_windowmanager.dart';
import 'dart:io' show Platform;

import 'api.dart';
import 'app_model.dart';
import 'theme.dart';
import 'app_shell.dart';
import 'screens/login_screen.dart';
import 'screens/wallet_screen.dart';
import 'screens/merchant_screen.dart';
import 'screens/links_screen.dart';
import 'screens/subscriptions_screen.dart';
import 'screens/vouchers_screen.dart';
import 'screens/vouchers_admin_screen.dart';
import 'screens/statement_screen.dart';
import 'screens/request_detail_screen.dart';

const String kAppLinkHost = String.fromEnvironment('APP_LINK_HOST', defaultValue: '');

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Future<void> start() async {
    final model = AppModel(tokenStore: TokenStore(), baseUrl: 'http://localhost:8080');
    await model.load();
    runApp(ChangeNotifierProvider(create: (_) => model, child: const App()));
  }

  const dsn = String.fromEnvironment('SENTRY_DSN', defaultValue: '');
  if (dsn.isNotEmpty) {
    await SentryFlutter.init((o) {
      o.dsn = dsn;
      o.tracesSampleRate = 0.2;
    });
  }
  // Screen security (Android): prevent screenshots/recents preview
  try { if (Platform.isAndroid) { await FlutterWindowManager.addFlags(FlutterWindowManager.FLAG_SECURE); } } catch (_) {}
  await start();
}

class App extends StatefulWidget { const App({super.key}); @override State<App> createState() => _AppState(); }

class _AppState extends State<App> {
  StreamSubscription? _linkSub;
  late GoRouter _router;

  @override
  void initState() {
    super.initState();
    final model = context.read<AppModel>();
    _router = _buildRouter(model);
    _initDeepLinks();
  }

  void _initDeepLinks() async {
    try { final initial = await getInitialLink(); if (initial != null) _handleLink(initial); } catch (_) {}
    _linkSub = uriLinkStream.listen((uri) { if (uri != null) _handleLink(uri.toString()); }, onError: (_) {});
  }

  void _handleLink(String link) {
    try {
      final uri = Uri.parse(link);
      final isPaymentsScheme = uri.scheme == 'payments' && uri.host == 'request' && uri.pathSegments.isNotEmpty;
      final isHttpsAppLink = uri.scheme == 'https' && uri.pathSegments.isNotEmpty &&
          (kAppLinkHost.isEmpty || uri.host == kAppLinkHost) && uri.pathSegments.first == 'request';
      if (isPaymentsScheme || isHttpsAppLink) {
        final id = uri.pathSegments.first;
        _router.go('/request/$id');
      }
    } catch (_) {}
  }

  @override
  void dispose() { _linkSub?.cancel(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final model = context.watch<AppModel>();
    return MaterialApp.router(
      title: 'Payments',
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: model.themeMode,
      routerConfig: _router,
    );
  }

  GoRouter _buildRouter(AppModel model) {
    return GoRouter(
      initialLocation: model.loggedIn ? '/wallet' : '/login',
      refreshListenable: model,
      redirect: (context, state) {
        final loggedIn = model.loggedIn;
        final loggingIn = state.uri.toString().startsWith('/login');
        if (!loggedIn && !loggingIn) return '/login';
        if (loggedIn && loggingIn) return '/wallet';
        return null;
      },
      routes: [
        GoRoute(
          path: '/login',
          builder: (context, state) => LoginScreen(api: model.api, tokenStore: model.tokenStore, onLoggedIn: () async { model.setLoggedIn(true); }),
        ),
        ShellRoute(
          builder: (context, state, child) => AppShell(child: _ScaffoldWithTopBar(child: child)),
          routes: [
            GoRoute(path: '/wallet', builder: (c, s) => WalletScreen(api: model.api, tokenStore: model.tokenStore, uuid: model.uuid)),
            GoRoute(path: '/merchant', builder: (c, s) => MerchantScreen(api: model.api, onChanged: () {})),
            GoRoute(path: '/vouchers', builder: (c, s) => VouchersScreen(api: model.api)),
            GoRoute(path: '/admin', builder: (c, s) => VouchersAdminScreen(api: model.api)),
            GoRoute(path: '/links', builder: (c, s) => LinksScreen(api: model.api)),
            GoRoute(path: '/subs', builder: (c, s) => SubscriptionsScreen(api: model.api)),
          ],
        ),
        GoRoute(path: '/statement', builder: (c, s) => StatementScreen(api: model.api)),
        GoRoute(path: '/request/:id', builder: (c, s) => RequestDetailScreen(api: model.api, requestId: s.pathParameters['id']!)),
      ],
    );
  }
}

class _ScaffoldWithTopBar extends StatelessWidget {
  final Widget child; const _ScaffoldWithTopBar({required this.child});
  @override
  Widget build(BuildContext context) {
    final model = context.watch<AppModel>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payments'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_ethernet),
            onPressed: () async {
              final ctrl = TextEditingController(text: model.baseUrl);
              final url = await showDialog<String>(
                context: context,
                builder: (_) => AlertDialog(
                  title: const Text('Set Base URL'),
                  content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'http://localhost:8080')),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
                    FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save')),
                  ],
                ),
              );
              if (url != null && url.isNotEmpty) { await model.setBaseUrl(url); }
            },
          ),
          PopupMenuButton<String>(
            onSelected: (v) {
              switch (v) {
                case 'light': model.setThemeMode(ThemeMode.light); break;
                case 'dark': model.setThemeMode(ThemeMode.dark); break;
                case 'system': model.setThemeMode(ThemeMode.system); break;
                case 'statement': GoRouter.of(context).go('/statement'); break;
              }
            },
            itemBuilder: (c) => const [
              PopupMenuItem(value: 'statement', child: Text('Statement')),
              PopupMenuDivider(),
              PopupMenuItem(value: 'light', child: Text('Light theme')),
              PopupMenuItem(value: 'dark', child: Text('Dark theme')),
              PopupMenuItem(value: 'system', child: Text('System theme')),
            ],
          ),
        ],
      ),
      body: child,
    );
  }
}
