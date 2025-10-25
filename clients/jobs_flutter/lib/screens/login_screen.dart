import 'package:flutter/material.dart';

import '../api.dart';

class LoginScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onLoggedIn;
  const LoginScreen({super.key, required this.api, required this.onLoggedIn});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _loading = false;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            FilledButton(
              onPressed: _loading ? null : () async {
                setState(() => _loading = true);
                try {
                  const phone = '+963900000001';
                  await widget.api.requestOtp(phone);
                  await widget.api.verifyOtp(phone: phone, otp: '123456', name: 'User', role: 'seeker');
                  widget.onLoggedIn();
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
                } finally {
                  if (mounted) setState(() => _loading = false);
                }
              },
              child: const Text('Continue'),
            ),
          ]),
        ),
      ),
    );
  }
}
