import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/restaurants_screen.dart';
import 'screens/home_screen.dart';
import 'screens/cart_screen.dart';
import 'screens/orders_screen.dart';
import 'screens/admin_screen.dart';
import 'screens/courier_screen.dart';
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
  String _baseUrl = 'http://localhost:8090';
  static const _baseUrlKey = 'food_base_url';

  @override
  void initState() {
    super.initState();
    _api = ApiClient(baseUrl: _baseUrl, tokenStore: _tokenStore);
    _loadBaseUrl();
  }

  Future<void> _loadBaseUrl() async {
    final p = await SharedPreferences.getInstance();
    final saved = p.getString(_baseUrlKey);
    if (saved != null && saved.isNotEmpty) {
      setState(() { _baseUrl = saved; _api.baseUrl = _baseUrl; });
    }
  }

  Future<void> _updateBaseUrl(String url) async {
    final v = url.trim();
    setState(() { _baseUrl = v; _api.baseUrl = _baseUrl; });
    final p = await SharedPreferences.getInstance();
    await p.setString(_baseUrlKey, v);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Food',
      themeMode: ThemeMode.dark,
      darkTheme: SharedTheme.dark(),
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.orange),
      home: FutureBuilder<String?>(
        future: _tokenStore.getToken(),
        builder: (context, snap) {
          final token = snap.data;
          final loggedIn = token != null && token.isNotEmpty;
          return Scaffold(
            appBar: AppBar(title: const Text('Food Delivery'), actions: [
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
                      content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'http://localhost:8090')),
                      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save'))],
                    ),
                  );
                  if (url != null && url.isNotEmpty) await _updateBaseUrl(url);
                },
              )
            ]),
            body: loggedIn
                ? DefaultTabController(
                    length: 5,
                    child: Column(children: [
                      const TabBar(tabs: [Tab(text: 'Home'), Tab(text: 'Cart'), Tab(text: 'Orders'), Tab(text: 'Admin'), Tab(text: 'Courier')]),
                      Expanded(
                        child: TabBarView(children: [
                          HomeScreen(api: _api),
                          CartScreen(api: _api),
                          OrdersScreen(api: _api),
                          AdminScreen(api: _api),
                          CourierScreen(api: _api),
                        ]),
                      )
                    ]),
                  )
                : LoginScreen(api: _api, onLoggedIn: () => setState(() {})),
          );
        },
      ),
    );
  }
}
