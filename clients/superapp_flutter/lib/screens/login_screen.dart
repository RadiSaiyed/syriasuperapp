import 'package:flutter/material.dart';
import '../services.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _username = TextEditingController(text: 'admin');
  final _password = TextEditingController(text: 'admin');
  final _regUsername = TextEditingController();
  final _regPassword = TextEditingController();
  final _regPhone = TextEditingController();
  final _regName = TextEditingController();
  bool _loading = false;

  void _toast(String m) { if (!mounted) return; showToast(context, m); }

  Future<void> _devLogin() async {
    final u = _username.text.trim();
    final p = _password.text.trim();
    if (u.isEmpty || p.isEmpty) { _toast('Enter username and password'); return; }
    setState(() => _loading = true);
    try {
      await devLogin(username: u, password: p);
      // Token is already propagated in devLogin; optionally probe Payments
      await validateTokenAndMaybePropagate(service: 'payments', propagateAll: true);
      // Offer enabling biometric unlock if supported
      try {
        final auth = LocalAuthentication();
        if (await auth.isDeviceSupported() && await auth.canCheckBiometrics) {
          if (!mounted) return;
          final enable = await showDialog<bool>(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('Enable biometric unlock?'),
              content: const Text('Quickly unlock with Face ID / Touch ID.'),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('No')),
                FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Yes')),
              ],
            ),
          );
          if (enable == true) {
            final prefs = await SharedPreferences.getInstance();
            await prefs.setBool('biometric_enabled', true);
          }
        }
      } catch (_) {}
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/home');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Dev login failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _register() async {
    final u = _regUsername.text.trim();
    final p = _regPassword.text.trim();
    final ph = _regPhone.text.trim();
    final nm = _regName.text.trim();
    if (u.isEmpty || p.isEmpty || ph.isEmpty) {
      _toast('Enter username, password, and phone');
      return;
    }
    setState(() => _loading = true);
    try {
      await registerUser(username: u, password: p, phone: ph, name: nm.isEmpty ? null : nm);
      await validateTokenAndMaybePropagate(service: 'payments', propagateAll: true);
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/home');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Registration failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _passwordLogin() async {
    final u = _username.text.trim();
    final p = _password.text.trim();
    if (u.isEmpty || p.isEmpty) { _toast('Enter username and password'); return; }
    setState(() => _loading = true);
    try {
      await passwordLogin(username: u, password: p);
      await validateTokenAndMaybePropagate(service: 'payments', propagateAll: true);
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/home');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Login failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Login / Registration'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_loading) const LinearProgressIndicator(),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Create account', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                TextField(controller: _regUsername, decoration: const InputDecoration(labelText: 'Username')),
                const SizedBox(height: 8),
                TextField(controller: _regPassword, decoration: const InputDecoration(labelText: 'Password'), obscureText: true),
                const SizedBox(height: 8),
                TextField(controller: _regPhone, decoration: const InputDecoration(labelText: 'Phone (+963...)'), keyboardType: TextInputType.phone),
                const SizedBox(height: 8),
                TextField(controller: _regName, decoration: const InputDecoration(labelText: 'Name (optional)')),
                const SizedBox(height: 8),
                FilledButton(onPressed: _loading ? null : _register, child: const Text('Sign up')),
              ]),
            ),
          ),
          const SizedBox(height: 12),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Login with username/password', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                TextField(controller: _username, decoration: const InputDecoration(labelText: 'Username')),
                const SizedBox(height: 8),
                TextField(controller: _password, decoration: const InputDecoration(labelText: 'Password'), obscureText: true),
                const SizedBox(height: 8),
                FilledButton(onPressed: _loading ? null : _passwordLogin, child: const Text('Continue')),
              ]),
            ),
          ),
          const SizedBox(height: 12),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Dev login (shortcuts)', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                const Text('For local dev only. Maps to test users.'),
                const SizedBox(height: 8),
                FilledButton(onPressed: _loading ? null : _devLogin, child: const Text('Dev Login')),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}
