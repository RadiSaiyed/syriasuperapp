import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flights_flutter/api.dart';
import 'package:flights_flutter/screens/login_screen.dart';

void main() {
  testWidgets('Login screen renders', (tester) async {
    final api = ApiClient(baseUrl: 'http://localhost:8092', tokenStore: TokenStore());
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: LoginScreen(api: api, onLoggedIn: () {}))));
    expect(find.text('Login'), findsOneWidget);
    expect(find.textContaining('OTP'), findsOneWidget);
    expect(find.byType(TextField), findsWidgets);
  });
}

