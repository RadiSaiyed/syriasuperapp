// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:payments_flutter/main.dart';
import 'package:payments_flutter/app_model.dart';
import 'package:payments_flutter/api.dart';

void main() {
  testWidgets('App renders title', (tester) async {
    final model = AppModel(tokenStore: TokenStore(), baseUrl: 'http://localhost:8080');
    // Ensure we land on a routed page with a Scaffold/AppBar
    model.setLoggedIn(true);
    await tester.pumpWidget(ChangeNotifierProvider(create: (_) => model, child: const App()));
    await tester.pump();
    // AppBar title
    expect(find.text('Payments'), findsOneWidget);
  });
}
