import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_ui/shared_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/search_screen.dart';
import 'screens/bookings_screen.dart';

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
  String _baseUrl = 'http://localhost:8092';
  int _tab = 0;
  static const _baseUrlKey = 'flights_base_url';

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
      setState(() {
        _baseUrl = saved;
        _api.baseUrl = _baseUrl;
      });
    }
  }

  Future<void> _updateBaseUrl(String url) async {
    final v = url.trim();
    setState(() {
      _baseUrl = v;
      _api.baseUrl = _baseUrl;
    });
    final p = await SharedPreferences.getInstance();
    await p.setString(_baseUrlKey, v);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flights MVP',
      themeMode: ThemeMode.dark,
      darkTheme: SharedTheme.dark(),
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
      home: FutureBuilder<String?>(
        future: _tokenStore.getToken(),
        builder: (context, snap) {
          final token = snap.data;
          final loggedIn = token != null && token.isNotEmpty;
          return Scaffold(
            appBar: AppBar(title: const Text('Flights MVP'), actions: [
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
                      content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'http://localhost:8092')),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
                        FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save')),
                      ],
                    ),
                  );
                  if (url != null && url.isNotEmpty) await _updateBaseUrl(url);
                },
              )
            ]),
            body: loggedIn
                ? Column(children: [
                    NavigationBar(
                      selectedIndex: _tab,
                      onDestinationSelected: (i) => setState(() => _tab = i),
                      destinations: const [
                        NavigationDestination(icon: Icon(Icons.search), label: 'Search'),
                        NavigationDestination(icon: Icon(Icons.receipt_long), label: 'Bookings'),
                      ],
                    ),
                    const Divider(height: 1),
                    Expanded(child: _tab == 0 ? SearchScreen(api: _api) : BookingsScreen(api: _api)),
                  ])
                : LoginScreen(api: _api, onLoggedIn: () => setState(() {})),
          );
        },
      ),
    );
  }
}
