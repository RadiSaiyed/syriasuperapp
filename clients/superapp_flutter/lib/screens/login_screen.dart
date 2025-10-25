import 'package:flutter/material.dart';
import '../services.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../ui/glass.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phone = TextEditingController(text: '+963900000001');
  final _otp = TextEditingController(text: '123456');
  final _name = TextEditingController();
  bool _loading = false;

  void _toast(String m) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _requestOtp() async {
    final p = _phone.text.trim();
    if (p.isEmpty) return;
    setState(() => _loading = true);
    try {
      await requestOtp('payments', p);
      _toast('OTP sent (dev: 123456)');
    } catch (e) {
      _toast('OTP failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _verify() async {
    final p = _phone.text.trim();
    final o = _otp.text.trim();
    if (p.isEmpty || o.isEmpty) { _toast('Enter phone and OTP'); return; }
    setState(() => _loading = true);
    try {
      await verifyOtp('payments', p, o, name: _name.text.trim().isEmpty ? null : _name.text.trim());
      // Also sign into Chat (dev OTP works without prior request)
      try {
        await verifyOtp('chat', p, o, name: _name.text.trim().isEmpty ? null : _name.text.trim());
      } catch (_) { /* ignore; chat may be offline */ }
      // Propagate token to all services (single-login)
      final t = await MultiTokenStore().get('payments');
      if (t != null && t.isNotEmpty) {
        await MultiTokenStore().setAll(t);
      }
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
      _toast('Login failed: $e');
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
                const Text('Sign in with phone', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                TextField(controller: _phone, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Phone (+963...)')),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: TextField(controller: _otp, decoration: const InputDecoration(labelText: 'OTP'))),
                  const SizedBox(width: 8),
                  OutlinedButton(onPressed: _loading ? null : _requestOtp, child: const Text('Request OTP')),
                ]),
                const SizedBox(height: 8),
                TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name (optional)')),
                const SizedBox(height: 8),
                FilledButton(onPressed: _loading ? null : _verify, child: const Text('Continue')),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}
