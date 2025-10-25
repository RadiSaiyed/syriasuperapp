import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:stays_flutter/api.dart';
import 'package:stays_flutter/screens/guest_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8088', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> searchAvailability({String? city, required String checkIn, required String checkOut, required int guests}) async => [
    {'property_id':'p1','property_name':'Sunrise','unit_id':'u1','unit_name':'Deluxe','capacity':2,'available_units':1,'nightly_price_cents':50000,'total_cents':100000},
  ];

  @override
  Future<Map<String, dynamic>> createReservation({required String unitId, required String checkIn, required String checkOut, required int guests}) async => {
    'id':'r1','property_id':'p1','unit_id':unitId,'status':'created','check_in':checkIn,'check_out':checkOut,'guests':guests,'total_cents':100000,
  };

  @override
  Future<List<Map<String, dynamic>>> myReservations() async => [
    {'id':'r1','property_id':'p1','unit_id':'u1','status':'created','check_in':'2025-01-01','check_out':'2025-01-03','guests':2,'total_cents':100000},
  ];
}

void main() {
  testWidgets('GuestScreen shows search and reservations tabs', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: GuestScreen(api: api))));
    await tester.pump();
    expect(find.text('Search'), findsWidgets);
    expect(find.text('My Reservations'), findsWidgets);
    await tester.tap(find.text('Search').first);
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    expect(find.text('Search'), findsWidgets);
  });
}
