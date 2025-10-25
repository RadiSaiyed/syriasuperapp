import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:freight_flutter/api.dart';
import 'package:freight_flutter/screens/carrier_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8085', tokenStore: TokenStore());

  @override
  Future<void> carrierApply({String? companyName}) async {}

  @override
  Future<List<Map<String, dynamic>>> availableLoads() async {
    return [
      {
        'id': 'l1',
        'origin': 'Damascus',
        'destination': 'Aleppo',
        'weight_kg': 1000,
        'price_cents': 50000,
        'status': 'posted',
      }
    ];
  }

  Map<String, dynamic> _current(String status) => {
    'id': 'l1',
    'origin': 'Damascus',
    'destination': 'Aleppo',
    'weight_kg': 1000,
    'price_cents': 50000,
    'status': status,
  };

  @override
  Future<Map<String, dynamic>> acceptLoad(String loadId) async => _current('assigned');
  @override
  Future<Map<String, dynamic>> pickupLoad(String loadId) async => _current('picked_up');
  @override
  Future<Map<String, dynamic>> inTransitLoad(String loadId) async => _current('in_transit');
  @override
  Future<Map<String, dynamic>> deliverLoad(String loadId) async => {
    ..._current('delivered'),
    'payment_request_id': 'req-xyz',
  };
}

void main() {
  testWidgets('Carrier flow shows Open in Payments CTA after deliver', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: CarrierScreen(api: api))));

    // Load of available loads
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Accept'), findsOneWidget);

    // Accept
    await tester.tap(find.text('Accept'));
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.textContaining('Current Load'), findsOneWidget);

    // Pickup → In transit → Deliver
    await tester.tap(find.text('Pickup'));
    await tester.pump(const Duration(milliseconds: 30));
    await tester.tap(find.text('In transit'));
    await tester.pump(const Duration(milliseconds: 30));
    await tester.tap(find.text('Deliver'));
    await tester.pump(const Duration(milliseconds: 80));

    // Bottom sheet contains Open in Payments
    expect(find.text('Open in Payments'), findsOneWidget);
  });
}

