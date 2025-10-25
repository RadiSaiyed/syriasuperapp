import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import '../security/pin_storage.dart';

class AuthGate {
  static final _la = LocalAuthentication();
  static final _pin = PinStorage();

  static Future<bool> verifyForAction(BuildContext context, {String reason = 'Authorize payment'}) async {
    try {
      final bioEnabled = await _pin.isBiometricEnabled();
      if (bioEnabled) {
        final canCheck = await _la.canCheckBiometrics;
        final isSupported = await _la.isDeviceSupported();
        if (canCheck && isSupported) {
          final ok = await _la.authenticate(localizedReason: reason, options: const AuthenticationOptions(biometricOnly: true));
          if (ok) return true;
        }
      }
    } catch (_) {}
    // Fallback to PIN
    final has = await _pin.hasPin();
    if (!has) {
      final set = await _showSetPinDialog(context);
      if (!set) return false;
    }
    final ok = await _showEnterPinDialog(context);
    return ok;
  }

  static Future<bool> _showSetPinDialog(BuildContext context) async {
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
              if (p1.length < 4 || p1.length > 8 || !RegExp(r'^\d{4,8}\$').hasMatch(p1)) {
                setState(() => err = 'PIN must be 4-8 digits');
                return;
              }
              if (p1 != p2) { setState(() => err = 'PINs do not match'); return; }
              await _pin.setPin(p1);
              // ignore: use_build_context_synchronously
              Navigator.pop(context, true);
            }, child: const Text('Save')),
          ],
        );
      })
    );
    return ok ?? false;
  }

  static Future<bool> _showEnterPinDialog(BuildContext context) async {
    final ctrl = TextEditingController();
    String? err;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (context, setState) {
        return AlertDialog(
          title: const Text('Enter App PIN'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: ctrl, obscureText: true, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'PIN')),
            if (err != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(err!, style: const TextStyle(color: Colors.red)))
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () async {
              final p = ctrl.text.trim();
              final ok = await _pin.verifyPin(p);
              if (!ok) { setState(() => err = 'Invalid PIN'); return; }
              // ignore: use_build_context_synchronously
              Navigator.pop(context, true);
            }, child: const Text('Confirm')),
          ],
        );
      })
    );
    return ok ?? false;
  }
}

