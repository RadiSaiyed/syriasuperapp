import 'package:flutter/material.dart';
import '../api.dart';
import '../l10n/app_localizations.dart';

class LoginScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onLoggedIn;
  const LoginScreen({super.key, required this.api, required this.onLoggedIn});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _loading = false;
  final _userCtrl = TextEditingController(text: 'driver');
  final _passCtrl = TextEditingController(text: 'driver');

  Future<void> _login() async {
    setState(() => _loading = true);
    try {
      final u = _userCtrl.text.trim();
      final p = _passCtrl.text;
      if (u.isEmpty || p.isEmpty) {
        throw Exception('Please enter username and password');
      }
      await widget.api.devLogin(username: u, password: p);
      widget.onLoggedIn();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(loc.appTitleDriver, textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 12),
              TextField(
                controller: _userCtrl,
                decoration: const InputDecoration(labelText: 'Username'),
                textInputAction: TextInputAction.next,
                enabled: !_loading,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _passCtrl,
                decoration: const InputDecoration(labelText: 'Password'),
                obscureText: true,
                enabled: !_loading,
                onSubmitted: (_) => _loading ? null : _login(),
              ),
              const SizedBox(height: 16),
              FilledButton(onPressed: _loading ? null : _login, child: const Text('Login')),
            ],
          ),
        ),
      ),
    );
  }
}
