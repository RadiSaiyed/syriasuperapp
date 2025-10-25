import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:jobs_flutter/api.dart';
import 'package:jobs_flutter/screens/login_screen.dart';

void main() {
  testWidgets('Jobs login screen renders basic controls', (tester) async {
    final api = ApiClient(baseUrl: 'http://localhost:8087', tokenStore: TokenStore());
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: LoginScreen(api: api, onLoggedIn: () {}))));
    expect(find.textContaining('Phone'), findsOneWidget);
    expect(find.text('Request OTP'), findsOneWidget);
  });
}

