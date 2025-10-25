import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/guest_screen.dart';
import 'screens/host_screen.dart';
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
  String _baseUrl = 'http://localhost:8088';
  static const _baseUrlKey = 'stays_base_url';
  String _role = 'guest';

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
      title: 'Stays',
      themeMode: ThemeMode.dark,
      darkTheme: SharedTheme.dark(),
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
      home: FutureBuilder<String?>(
        future: _tokenStore.getToken(),
        builder: (context, snap) {
          final token = snap.data;
          final loggedIn = token != null && token.isNotEmpty;
          return Scaffold(
            appBar: AppBar(title: const Text('Stays'), actions: [
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
                      content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'http://localhost:8088')),
                      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save'))],
                    ),
                  );
                  if (url != null && url.isNotEmpty) await _updateBaseUrl(url);
                },
              )
            ]),
            body: loggedIn
                ? Column(children: [
                    Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      const SizedBox(width: 8),
                      const Text('Role:'),
                      const SizedBox(width: 8),
                      DropdownButton<String>(
                        value: _role,
                        items: const [DropdownMenuItem(value: 'guest', child: Text('Guest')), DropdownMenuItem(value: 'host', child: Text('Host'))],
                        onChanged: (v) => setState(() => _role = v ?? 'guest'),
                      ),
                    ]),
                    Expanded(child: _role == 'host' ? HostScreen(api: _api) : GuestScreen(api: _api)),
                  ])
                : LoginScreen(api: _api, onLoggedIn: () => setState(() {})),
          );
        },
      ),
    );
  }
}
