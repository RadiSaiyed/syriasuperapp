import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import '../security/pin_storage.dart';

class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key});
  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  final _pin = PinStorage();
  final _la = LocalAuthentication();
  bool _bioAvailable = false;
  bool _bioEnabled = false;
  bool _hasPin = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final hasPin = await _pin.hasPin();
    final enabled = await _pin.isBiometricEnabled();
    bool available = false;
    try { available = await _la.canCheckBiometrics; } catch (_) {}
    if (mounted) setState(() { _hasPin = hasPin; _bioEnabled = enabled; _bioAvailable = available; });
  }

  Future<void> _setPin() async {
    final ctrl1 = TextEditingController();
    final ctrl2 = TextEditingController();
    String? err;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (context, setState) {
        return AlertDialog(
          title: const Text('Set App PIN'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: ctrl1, obscureText: true, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'PIN (4-8 digits)')),
            TextField(controller: ctrl2, obscureText: true, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Confirm PIN')),
            if (err != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(err!, style: const TextStyle(color: Colors.red)))
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () async {
              final p1 = ctrl1.text.trim();
              final p2 = ctrl2.text.trim();
              if (p1.length < 4 || p1.length > 8 || !RegExp(r'^\d{4,8}\$').hasMatch(p1)) { setState(() => err = 'PIN must be 4-8 digits'); return; }
              if (p1 != p2) { setState(() => err = 'PINs do not match'); return; }
              await _pin.setPin(p1);
              // ignore: use_build_context_synchronously
              Navigator.pop(context, true);
            }, child: const Text('Save')),
          ],
        );
      }),
    );
    if (ok == true) _load();
  }

  Future<void> _clearPin() async {
    await _pin.clearPin();
    _load();
  }

  Future<void> _toggleBio(bool v) async {
    await _pin.setBiometricEnabled(v);
    setState(() => _bioEnabled = v);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Security')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('App PIN', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: Text(_hasPin ? 'PIN is set' : 'No PIN set')),
            if (_hasPin)
              OutlinedButton(onPressed: _clearPin, child: const Text('Remove'))
            else
              FilledButton(onPressed: _setPin, child: const Text('Set PIN')),
          ]),
          const SizedBox(height: 24),
          const Text('Biometrics', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: Text(_bioAvailable ? 'Biometric sensor available' : 'No biometrics available')),
            Switch(value: _bioEnabled, onChanged: _bioAvailable ? _toggleBio : null),
          ]),
          const SizedBox(height: 12),
          const Text('Payments will require PIN or biometrics.'),
        ]),
      ),
    );
  }
}

