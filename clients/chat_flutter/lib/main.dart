import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/contacts_screen.dart';
import 'screens/conversations_screen.dart';
import 'package:shared_ui/shared_ui.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

class App extends StatefulWidget {
  final String? initialBaseUrl;
  final TokenStore? tokenStore;
  final DeviceStore? deviceStore;
  const App({super.key, this.initialBaseUrl, this.tokenStore, this.deviceStore});
  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  late final TokenStore _tokenStore;
  late final DeviceStore _deviceStore;
  late ApiClient _api;
  late String _baseUrl;
  static const _baseUrlKey = 'chat_base_url';

  @override
  void initState() {
    super.initState();
    _tokenStore = widget.tokenStore ?? TokenStore();
    _deviceStore = widget.deviceStore ?? DeviceStore();
    _baseUrl = widget.initialBaseUrl ?? 'http://localhost:8091';
    _api = ApiClient(baseUrl: _baseUrl, tokenStore: _tokenStore, deviceStore: _deviceStore);
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
      title: 'Chat',
      themeMode: ThemeMode.dark,
      darkTheme: SharedTheme.dark(),
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blueGrey),
      home: FutureBuilder<String?>(
        future: _tokenStore.getToken(),
        builder: (context, snap) {
          final token = snap.data;
          final loggedIn = token != null && token.isNotEmpty;
          final nav = Navigator.of(context);
          final canPop = nav.canPop();
          return Scaffold(
            appBar: AppBar(
                leading: canPop
                    ? IconButton(
                        icon: const Icon(Icons.arrow_back_ios_new),
                        onPressed: () => nav.maybePop(),
                        tooltip: 'Back',
                      )
                    : null,
                title: const Text('Chat'),
                actions: [
              IconButton(
                icon: const Icon(Icons.settings_ethernet),
                tooltip: 'Set Base URL',
                onPressed: () async {
                  final ctrl = TextEditingController(text: _baseUrl);
                  final url = await showDialog<String>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: const Text('Set Base URL'),
                      content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'http://localhost:8091')),
                      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save'))],
                    ),
                  );
                  if (url != null && url.isNotEmpty) await _updateBaseUrl(url);
                },
              )
            ]),
            body: loggedIn
                ? DefaultTabController(
                    length: 2,
                    child: Column(children: [
                      const TabBar(tabs: [Tab(text: 'Conversations'), Tab(text: 'Contacts')]),
                      Expanded(child: TabBarView(children: [ConversationsScreen(api: _api), ContactsScreen(api: _api)])),
                    ]),
                  )
                : LoginScreen(api: _api, onLoggedIn: () => setState(() {})),
          );
        },
      ),
    );
  }
}
