import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:stays_flutter/api.dart';
import 'package:stays_flutter/screens/host_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8088', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> myProperties() async => [
    {'id':'p1','name':'Sunrise Hotel','type':'hotel','city':'Damascus'},
  ];

  @override
  Future<List<Map<String, dynamic>>> listUnits(String propertyId) async => [
    {'id':'u1','property_id':propertyId,'name':'Deluxe','capacity':2,'total_units':2,'price_cents_per_night':50000,'active':true},
  ];

  @override
  Future<List<Map<String, dynamic>>> hostReservations() async => [];
}

void main() {
  testWidgets('HostScreen shows properties and units', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: HostScreen(api: api))));
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    expect(find.text('Sunrise Hotel'), findsOneWidget);
    // expand first tile
    await tester.tap(find.text('Sunrise Hotel'));
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    expect(find.text('Deluxe'), findsOneWidget);
  });
}
