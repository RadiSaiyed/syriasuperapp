import 'package:flutter/material.dart';
import 'package:chat_flutter/api.dart' as chat_api;
import 'package:chat_flutter/main.dart' as chat_app;
import 'package:chat_flutter/screens/login_screen.dart' as chat_login;
import 'package:chat_flutter/screens/conversations_screen.dart' as chat_convos;
import 'package:chat_flutter/screens/contacts_screen.dart' as chat_contacts;
import 'package:shared_preferences/shared_preferences.dart';

import '../services.dart';

class ChatModule {
  const ChatModule._();

  static Widget build() {
    // Use embedded variant with a Super‑App AppBar (back button)
    return const _ChatEmbeddedHome();
  }
}

class _SuperAppChatTokenStore extends chat_api.TokenStore {
  final MultiTokenStore multiStore;
  _SuperAppChatTokenStore(this.multiStore);

  @override
  Future<String?> getToken() => getTokenFor('chat', store: multiStore);

  @override
  Future<void> setToken(String token) => multiStore.set('chat', token);

  @override
  Future<void> clear() => multiStore.clear('chat');
}

class _ChatEmbeddedHome extends StatefulWidget {
  const _ChatEmbeddedHome();
  @override
  State<_ChatEmbeddedHome> createState() => _ChatEmbeddedHomeState();
}

class _ChatEmbeddedHomeState extends State<_ChatEmbeddedHome> {
  late final _tokenStore = _SuperAppChatTokenStore(MultiTokenStore());
  late final _deviceStore = chat_api.DeviceStore();
  late final chat_api.ApiClient _api;
  late String _baseUrl;
  static const _baseUrlKey = 'chat_base_url';

  @override
  void initState() {
    super.initState();
    _baseUrl = ServiceConfig.baseUrl('chat');
    _api = chat_api.ApiClient(baseUrl: _baseUrl, tokenStore: _tokenStore, deviceStore: _deviceStore);
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
    return FutureBuilder<String?>(
      future: _tokenStore.getToken(),
      builder: (context, snap) {
        final token = snap.data;
        final loggedIn = token != null && token.isNotEmpty;
        return Scaffold(
          appBar: AppBar(
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new),
              onPressed: () => Navigator.of(context).maybePop(),
              tooltip: 'Back',
            ),
            title: const Text('Chat'),
            actions: [
              if (loggedIn)
                IconButton(
                  icon: const Icon(Icons.logout),
                  tooltip: 'Logout',
                  onPressed: () async {
                    final ok = await showDialog<bool>(
                      context: context,
                      builder: (_) => AlertDialog(
                        title: const Text('Logout?'),
                        content: const Text('You will need to login again to access Chat.'),
                        actions: [
                          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Logout')),
                        ],
                      ),
                    );
                    if (ok == true) {
                      await _tokenStore.clear();
                      if (mounted) setState(() {});
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
                      content: TextField(
                        controller: ctrl,
                        decoration: const InputDecoration(hintText: 'http://localhost:8091'),
                      ),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
                        FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Save')),
                      ],
                    ),
                  );
                  if (url != null && url.isNotEmpty) await _updateBaseUrl(url);
                },
              )
            ],
          ),
          body: loggedIn
              ? DefaultTabController(
                  length: 2,
                  child: Column(
                    children: [
                      const TabBar(tabs: [Tab(text: 'Conversations'), Tab(text: 'Contacts')]),
                      Expanded(
                        child: TabBarView(
                          children: [
                            chat_convos.ConversationsScreen(api: _api),
                            chat_contacts.ContactsScreen(api: _api),
                          ],
                        ),
                      ),
                    ],
                  ),
                )
              : chat_login.LoginScreen(api: _api, onLoggedIn: () => setState(() {})),
        );
      },
    );
  }
}
