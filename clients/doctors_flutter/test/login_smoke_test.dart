import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:doctors_flutter/api.dart';
import 'package:doctors_flutter/screens/login_screen.dart';

void main() {
  testWidgets('Doctors login screen renders', (tester) async {
    final api = ApiClient(baseUrl: 'http://localhost:8089', tokenStore: TokenStore());
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: LoginScreen(api: api, onLoggedIn: () {}))));
    expect(find.text('Request OTP'), findsOneWidget);
    expect(find.byType(TextField), findsWidgets);
  });
}

