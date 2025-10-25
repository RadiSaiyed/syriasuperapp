import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:food_flutter/api.dart';
import 'package:food_flutter/screens/restaurants_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8090', tokenStore: TokenStore());
  @override
  Future<List<Map<String, dynamic>>> listRestaurants() async => [{'id':'r1','name':'Damascus Eats','city':'Damascus'}];
}

void main() {
  testWidgets('Shows restaurants', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: RestaurantsScreen(api: api))));
    await tester.pump();
    expect(find.text('Damascus Eats'), findsOneWidget);
  });
}

