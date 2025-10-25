import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'services.dart';

/// Ensures a user is logged in (by checking for an access token).
/// Returns true if logged in; otherwise navigates to the central login
/// screen and returns false.
Future<bool> ensureLoggedIn(BuildContext context, {String service = 'payments'}) async {
  final t = await getTokenFor(service);
  if (t != null && t.isNotEmpty) return true;
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Bitte zuerst anmelden')));
    Navigator.of(context).pushNamed('/login');
  }
  return false;
}

/// If biometrics are enabled in settings, request biometric authentication.
/// Returns true if either not enabled or authentication succeeds.
Future<bool> requireBiometricIfEnabled(BuildContext context, {String? reason}) async {
  try {
    final prefs = await SharedPreferences.getInstance();
    final enabled = prefs.getBool('biometric_enabled') ?? false;
    if (!enabled) return true;
    final lang = WidgetsBinding.instance.platformDispatcher.locale.languageCode.toLowerCase();
    final prompt = reason ?? (lang == 'ar'
        ? 'تأكيد العملية باستخدام Face ID / Touch ID'
        : 'Confirm with Face ID / Touch ID');
    final auth = LocalAuthentication();
    final supp = await auth.isDeviceSupported();
    final can = await auth.canCheckBiometrics;
    if (!supp || !can) return true; // treat as pass if not available
    final ok = await auth.authenticate(
      localizedReason: prompt,
      options: const AuthenticationOptions(biometricOnly: true, stickyAuth: true),
    );
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Abgebrochen')));
    }
    return ok;
  } catch (_) {
    // On error, fail closed to be safe
    return false;
  }
}

/// Convenience: ensure logged in then, if requested, require biometric.
Future<bool> guardAction(BuildContext context, {String service = 'payments', bool biometric = true, String? reason}) async {
  final authed = await ensureLoggedIn(context, service: service);
  if (!authed) return false;
  if (!biometric) return true;
  return await requireBiometricIfEnabled(context, reason: reason);
}
// ignore_for_file: use_build_context_synchronously
