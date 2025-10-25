import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:bus_flutter/api.dart';
import 'package:bus_flutter/screens/search_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8082', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> searchTrips({required String origin, required String destination, required DateTime date}) async {
    return [
      {
        'id': 't1',
        'operator_name': 'Test Operator',
        'origin': origin,
        'destination': destination,
        'depart_at': DateTime.now().toIso8601String(),
        'arrive_at': null,
        'price_cents': 10000,
        'seats_available': 10,
      }
    ];
  }

  @override
  Future<Map<String, dynamic>> createBooking({required String tripId, int seatsCount = 1}) async {
    return {
      'id': 'b1',
      'status': 'reserved',
      'payment_request_id': 'req-abc',
    };
  }
}

void main() {
  testWidgets('Search/Book shows Open in Payments CTA', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SearchScreen(api: api))));

    // Tap Search
    await tester.tap(find.text('Search'));
    await tester.pump(const Duration(milliseconds: 50));

    // Expect at least one Book button
    expect(find.text('Book'), findsWidgets);

    // Tap Book
    await tester.tap(find.text('Book').first);
    await tester.pump(const Duration(milliseconds: 50));

    // Bottom sheet contains Open in Payments
    expect(find.text('Open in Payments'), findsOneWidget);
  });
}
