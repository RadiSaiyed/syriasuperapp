import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:utilities_flutter/api.dart';
import 'package:utilities_flutter/screens/login_screen.dart';

void main() {
  testWidgets('Login screen renders basic fields', (tester) async {
    final api = ApiClient(baseUrl: 'http://localhost:8084', tokenStore: TokenStore());
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: LoginScreen(api: api, onLoggedIn: () {}))));

    expect(find.text('Login'), findsOneWidget);
    expect(find.byType(TextField), findsWidgets);
    expect(find.textContaining('OTP'), findsOneWidget);
    expect(find.text('Request OTP'), findsOneWidget);
  });
}
