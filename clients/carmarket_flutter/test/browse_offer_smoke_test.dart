import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:carmarket_flutter/api.dart';
import 'package:carmarket_flutter/screens/browse_screen.dart';

class _FakeApi extends ApiClient {
  bool offered = false;
  _FakeApi(): super(baseUrl: 'http://localhost:8086', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> browseListings() async {
    return [
      {
        'id': 'L1',
        'title': 'Toyota Corolla',
        'make': 'Toyota',
        'model': 'Corolla',
        'year': 2010,
        'price_cents': 3000000,
        'seller_user_id': 'S1',
      }
    ];
  }

  @override
  Future<Map<String, dynamic>> createOffer({required String listingId, required int amountCents}) async {
    offered = true;
    return {'id': 'O1', 'listing_id': listingId, 'buyer_user_id': 'B1', 'amount_cents': amountCents, 'status': 'pending'};
  }
}

void main() {
  testWidgets('Buyer can create offer from Browse', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: BrowseScreen(api: api))));

    // Allow initial load
    await tester.pump(const Duration(milliseconds: 50));

    // Tap Offer on the first listing
    expect(find.text('Offer'), findsOneWidget);
    await tester.tap(find.text('Offer'));
    await tester.pump(const Duration(milliseconds: 50));

    // Dialog 'Offer' button
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.tap(find.text('Offer').last);
    await tester.pump(const Duration(milliseconds: 80));

    // Fake API should have been called
    expect(api.offered, isTrue);
  });
}
