import 'package:flutter/material.dart';
import '../api.dart';
import '../ui/glass.dart';

class LoginScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onLoggedIn;
  const LoginScreen({super.key, required this.api, required this.onLoggedIn});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _nameCtrl = TextEditingController();
  bool _loading = false;

  Future<void> _devLogin() async {
    setState(() => _loading = true);
    try {
      const phone = '+963900000001';
      await widget.api.requestOtp(phone);
      await widget.api.verifyOtp(phone: phone, otp: '123456', name: _nameCtrl.text.trim().isEmpty ? 'User' : _nameCtrl.text.trim());
      widget.onLoggedIn();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Glass(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Login', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Name (optional)')),
        const SizedBox(height: 12),
        Row(children: [FilledButton(onPressed: _loading ? null : _devLogin, child: const Text('Continue'))]),
        if (_loading) const Padding(padding: EdgeInsets.only(top: 12), child: LinearProgressIndicator()),
      ])),
    );
  }
}
