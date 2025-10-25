import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:carmarket_flutter/api.dart';
import 'package:carmarket_flutter/screens/my_listings_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8086', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> myListings() async {
    return [
      {'id': 'L1', 'title': 'Toyota Corolla', 'make': 'Toyota', 'model': 'Corolla', 'year': 2010, 'price_cents': 3000000, 'seller_user_id': 'S1'},
    ];
  }

  @override
  Future<List<Map<String, dynamic>>> offersForListing(String listingId) async {
    return [
      {'id': 'O1', 'listing_id': listingId, 'buyer_user_id': 'B1', 'amount_cents': 2800000, 'status': 'pending'}
    ];
  }

  @override
  Future<Map<String, dynamic>> acceptOffer(String offerId) async {
    return {'id': offerId, 'listing_id': 'L1', 'buyer_user_id': 'B1', 'amount_cents': 2800000, 'status': 'accepted', 'payment_request_id': 'req-automarket'};
  }

  @override
  Future<Map<String, dynamic>> rejectOffer(String offerId) async => {'id': offerId};
}

void main() {
  testWidgets('Seller accept shows Open in Payments CTA', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: MyListingsScreen(api: api))));

    // Let initial loads finish
    await tester.pump(const Duration(milliseconds: 50));

    // Click Accept on the first offer
    expect(find.text('Accept'), findsOneWidget);
    await tester.tap(find.text('Accept'));
    await tester.pump(const Duration(milliseconds: 80));

    // Bottom sheet should offer Open in Payments
    expect(find.text('Open in Payments'), findsOneWidget);
  });
}
