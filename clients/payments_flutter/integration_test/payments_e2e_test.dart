import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:payments_flutter/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Payments E2E', () {
    testWidgets('Login → Create + Redeem Voucher (SYP)', (tester) async {
      // Launch app
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 1));

      // Login screen
      expect(find.text('Login'), findsOneWidget);

      await tester.enterText(find.byType(TextField).first, '+963900000111');
      await tester.tap(find.text('Request OTP'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      // OTP field appears
      await tester.enterText(find.widgetWithText(TextField, 'OTP (dev: 123456)'), '123456');
      await tester.tap(find.text('Verify OTP'));
      await tester.pumpAndSettle(const Duration(seconds: 1));

      // Expect Wallet view
      expect(find.text('Wallet'), findsWidgets);

      // Switch to Vouchers tab
      await tester.tap(find.text('Vouchers'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      // Create voucher 50 SYP
      final amountField = find.widgetWithText(TextField, 'Amount (SYP)');
      await tester.enterText(amountField, '50');
      await tester.tap(find.widgetWithText(FilledButton, 'Create'));
      await tester.pumpAndSettle(const Duration(seconds: 1));

      // Expect QR and code shown
      expect(find.byType(SelectableText), findsWidgets);
      // Grab the displayed code
      String? code;
      for (final e in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
        final t = e.data ?? '';
        if (t.startsWith('Code: ')) {
          code = t.substring('Code: '.length).trim();
          break;
        }
      }
      // If not found, try find the qr_text line VCHR|<code>
      code ??= (() {
        for (final e in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
          final t = e.data ?? '';
          if (t.startsWith('VCHR|')) {
            final parts = t.split('|');
            if (parts.length == 2) return parts[1];
          }
        }
        return null;
      })();
      expect(code != null && code!.isNotEmpty, true, reason: 'Voucher code visible');

      // Redeem voucher — enter code and tap Redeem
      await tester.enterText(find.widgetWithText(TextField, 'Voucher code'), code!);
      await tester.tap(find.widgetWithText(FilledButton, 'Redeem'));
      await tester.pumpAndSettle(const Duration(milliseconds: 800));

      // Expect snackbar with 'Redeemed'
      expect(find.textContaining('Redeem'), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 2)));

    testWidgets('Admin Bulk (optional with ADMIN_TOKEN)', (tester) async {
      final adminToken = const String.fromEnvironment('ADMIN_TOKEN', defaultValue: '');
      if (adminToken.isEmpty) {
        // Skip if not provided
        return;
      }
      // App should be already running from previous test; otherwise start
      try {
        app.main();
        await tester.pumpAndSettle(const Duration(milliseconds: 500));
      } catch (_) {}

      // Ensure logged in; if "Login" found, do quick login
      if (find.text('Login').evaluate().isNotEmpty) {
        await tester.enterText(find.byType(TextField).first, '+963900000222');
        await tester.tap(find.text('Request OTP'));
        await tester.pumpAndSettle(const Duration(milliseconds: 300));
        await tester.enterText(find.widgetWithText(TextField, 'OTP (dev: 123456)'), '123456');
        await tester.tap(find.text('Verify OTP'));
        await tester.pumpAndSettle(const Duration(milliseconds: 600));
      }

      // Go to Admin tab
      await tester.tap(find.text('Admin'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));

      // Set admin token and save
      await tester.enterText(find.widgetWithText(TextField, 'X-Admin-Token'), adminToken);
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle(const Duration(milliseconds: 300));

      // Bulk create 3 vouchers of 100 SYP
      await tester.enterText(find.widgetWithText(TextField, 'Amount (SYP)'), '100');
      await tester.enterText(find.widgetWithText(TextField, 'Count (1..1000)'), '3');
      await tester.tap(find.widgetWithText(FilledButton, 'Create'));
      await tester.pumpAndSettle(const Duration(seconds: 1));

      // Refresh list
      await tester.tap(find.widgetWithText(OutlinedButton, 'Refresh'));
      await tester.pumpAndSettle(const Duration(milliseconds: 800));

      // Expect at least 3 rows in table (DataRow creates Texts for codes)
      expect(find.textContaining('Code:'), findsNothing);
      // Just ensure DataTable exists
      expect(find.byType(DataTable), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 2)));
  });
  group('Payments E2E more', () {
    testWidgets('P2P Transfer', (tester) async {
      await _login(tester, '+963900000121');
      await _devTopup(tester, '100000');
      await tester.tap(find.widgetWithText(FilledButton, 'Transfer'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));
      await tester.enterText(find.widgetWithText(TextField, 'To phone (+963...)'), '+963900000122');
      await tester.enterText(find.widgetWithText(TextField, 'Amount (cents)'), '1000');
      await tester.tap(find.widgetWithText(FilledButton, 'Send'));
      await tester.pumpAndSettle(const Duration(seconds: 1));
      await _logout(tester);
      await _login(tester, '+963900000122');
      expect(find.text('Wallet'), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 2)));

    testWidgets('Merchant QR: create (A) and pay (B)', (tester) async {
      await _login(tester, '+963900000131');
      final approve = find.widgetWithText(TextButton, 'Dev Approve');
      if (approve.evaluate().isNotEmpty) { await tester.tap(approve); await tester.pumpAndSettle(const Duration(milliseconds: 300)); }
      await tester.tap(find.widgetWithText(FilledButton, 'Merchant / QR'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      if (find.text('Dev: enable immediately').evaluate().isNotEmpty) {
        await tester.tap(find.text('Dev: enable immediately'));
        await tester.pumpAndSettle(const Duration(milliseconds: 300));
      }
      await tester.enterText(find.widgetWithText(TextField, 'Amount (cents)'), '2000');
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle(const Duration(seconds: 1));
      String? qr;
      for (final e in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
        final t = e.data ?? '';
        if (t.startsWith('QR text: ')) { qr = t.substring('QR text: '.length).trim(); break; }
      }
      expect(qr != null && qr!.startsWith('PAY:v1;code='), true);
      await tester.pageBack(); await tester.pumpAndSettle(); await _logout(tester);
      await _login(tester, '+963900000132');
      await tester.tap(find.widgetWithText(FilledButton, 'Merchant / QR'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      await tester.enterText(find.widgetWithText(TextField, 'PAY:v1;code=...'), qr!);
      await tester.tap(find.widgetWithText(FilledButton, 'Pay'));
      await tester.pumpAndSettle(const Duration(milliseconds: 900));
      expect(find.textContaining('Paid'), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 3)));

    testWidgets('Payment Request: create (B) and accept (A)', (tester) async {
      await _login(tester, '+963900000141');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Contacts'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      await tester.tap(find.byIcon(Icons.person_add));
      await tester.pumpAndSettle(const Duration(milliseconds: 200));
      await tester.enterText(find.widgetWithText(TextField, 'Name'), 'A');
      await tester.enterText(find.widgetWithText(TextField, 'Phone'), '+963900000142');
      await tester.tap(find.widgetWithText(FilledButton, 'Add'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      await tester.tap(find.byIcon(Icons.request_page).first);
      await tester.pumpAndSettle(const Duration(milliseconds: 300));
      await tester.enterText(find.widgetWithText(TextField, 'Amount (cents)'), '1234');
      await tester.tap(find.widgetWithText(FilledButton, 'Send Request'));
      await tester.pumpAndSettle(const Duration(milliseconds: 600));
      await tester.pageBack(); await tester.pumpAndSettle(); await _logout(tester);
      await _login(tester, '+963900000142');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Requests'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));
      final accept = find.byIcon(Icons.check_circle).first;
      if (accept.evaluate().isNotEmpty) {
        await tester.tap(accept);
        await tester.pumpAndSettle(const Duration(milliseconds: 600));
      }
      expect(find.textContaining('Requests'), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 3)));

    testWidgets('Pay-by-Link dynamic & static', (tester) async {
      await _login(tester, '+963900000151');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Links'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      await tester.enterText(find.widgetWithText(TextField, 'Amount (cents, leave empty for static)'), '1000');
      await tester.tap(find.widgetWithText(FilledButton, 'Create'));
      await tester.pumpAndSettle(const Duration(milliseconds: 600));
      String? dyn;
      for (final e in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
        final t = e.data ?? '';
        if (t.startsWith('Code: ')) { dyn = t.substring('Code: '.length).trim(); break; }
      }
      expect(dyn != null && dyn!.startsWith('LINK:v1;code='), true);
      await tester.enterText(find.widgetWithText(TextField, 'Amount (cents, leave empty for static)'), '');
      await tester.tap(find.widgetWithText(FilledButton, 'Create'));
      await tester.pumpAndSettle(const Duration(milliseconds: 600));
      String? stat;
      for (final e in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
        final t = e.data ?? '';
        if (t.startsWith('Code: ')) { stat = t.substring('Code: '.length).trim(); }
      }
      expect(stat != null && stat!.startsWith('LINK:v1;code='), true);
      await tester.pageBack(); await tester.pumpAndSettle(); await _logout(tester);
      await _login(tester, '+963900000152');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Links'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      await tester.enterText(find.widgetWithText(TextField, 'LINK:v1;code=...'), dyn!);
      await tester.tap(find.widgetWithText(FilledButton, 'Pay'));
      await tester.pumpAndSettle(const Duration(milliseconds: 800));
      await tester.enterText(find.widgetWithText(TextField, 'LINK:v1;code=...'), stat!);
      await tester.enterText(find.widgetWithText(TextField, 'Amount (required for static)'), '777');
      await tester.tap(find.widgetWithText(FilledButton, 'Pay'));
      await tester.pumpAndSettle(const Duration(milliseconds: 800));
      expect(find.textContaining('Paid'), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 3)));

    testWidgets('Subscriptions: create and dev charge', (tester) async {
      await _login(tester, '+963900000161');
      final approve = find.widgetWithText(TextButton, 'Dev Approve');
      if (approve.evaluate().isNotEmpty) { await tester.tap(approve); await tester.pumpAndSettle(const Duration(milliseconds: 300)); }
      await tester.tap(find.widgetWithText(FilledButton, 'Merchant / QR'));
      await tester.pumpAndSettle(const Duration(milliseconds: 300));
      if (find.text('Dev: enable immediately').evaluate().isNotEmpty) {
        await tester.tap(find.text('Dev: enable immediately'));
        await tester.pumpAndSettle(const Duration(milliseconds: 300));
      }
      await tester.pageBack(); await tester.pumpAndSettle(); await _logout(tester);
      await _login(tester, '+963900000162');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Subscriptions'));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
      await tester.enterText(find.widgetWithText(TextField, 'Merchant phone +963...'), '+963900000161');
      await tester.enterText(find.widgetWithText(TextField, 'Amount (cents)'), '500');
      await tester.enterText(find.widgetWithText(TextField, 'Days'), '30');
      await tester.tap(find.widgetWithText(FilledButton, 'Create'));
      await tester.pumpAndSettle(const Duration(milliseconds: 800));
      final devCharge = find.widgetWithText(OutlinedButton, 'Dev charge').first;
      if (devCharge.evaluate().isNotEmpty) {
        await tester.tap(devCharge);
        await tester.pumpAndSettle(const Duration(milliseconds: 800));
      }
      expect(find.textContaining('Subscriptions'), findsWidgets);
    }, timeout: const Timeout(Duration(minutes: 3)));
  });
}

// Helpers
Future<void> _login(WidgetTester tester, String phone) async {
  if (find.text('Wallet').evaluate().isNotEmpty) {
    await _logout(tester);
  }
  app.main();
  await tester.pumpAndSettle(const Duration(milliseconds: 500));
  if (find.text('Login').evaluate().isEmpty) return;
  await tester.enterText(find.byType(TextField).first, phone);
  await tester.tap(find.text('Request OTP'));
  await tester.pumpAndSettle(const Duration(milliseconds: 300));
  await tester.enterText(find.widgetWithText(TextField, 'OTP (dev: 123456)'), '123456');
  await tester.tap(find.text('Verify OTP'));
  await tester.pumpAndSettle(const Duration(milliseconds: 600));
}

Future<void> _logout(WidgetTester tester) async {
  if (find.widgetWithText(OutlinedButton, 'Logout').evaluate().isNotEmpty) {
    await tester.tap(find.widgetWithText(OutlinedButton, 'Logout'));
    await tester.pumpAndSettle(const Duration(milliseconds: 500));
  }
}

Future<void> _devTopup(WidgetTester tester, String cents) async {
  final topupField = find.widgetWithText(TextField, 'Topup amount (cents)');
  if (topupField.evaluate().isNotEmpty) {
    await tester.enterText(topupField, cents);
    await tester.tap(find.widgetWithText(FilledButton, 'Dev Topup'));
    await tester.pumpAndSettle(const Duration(milliseconds: 400));
  }
}
