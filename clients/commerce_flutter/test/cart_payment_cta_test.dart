import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:commerce_flutter/api.dart';
import 'package:commerce_flutter/screens/cart_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8083', tokenStore: TokenStore());

  @override
  Future<Map<String, dynamic>> getCart() async {
    return {
      'id': 'c1',
      'items': [
        {
          'id': 'it1',
          'product_id': 'p1',
          'product_name': 'Test',
          'price_cents': 1000,
          'qty': 1,
          'subtotal_cents': 1000,
        }
      ],
      'total_cents': 1000,
    };
  }

  @override
  Future<Map<String, dynamic>> checkout() async {
    return {
      'id': 'o1',
      'status': 'created',
      'shop_id': 's1',
      'total_cents': 1000,
      'payment_request_id': 'req-123',
      'items': []
    };
  }

  @override
  Future<Map<String, dynamic>> updateCartItem({required String itemId, required int qty}) async => await getCart();
  @override
  Future<void> clearCart() async {}
}

void main() {
  testWidgets('Cart shows Open in Payments CTA after checkout', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: CartScreen(api: api))));
    // allow initial getCart
    await tester.pump();

    // Checkout button should be enabled
    expect(find.text('Checkout'), findsOneWidget);
    await tester.tap(find.text('Checkout'));
    // Let bottom sheet animate in
    await tester.pump(const Duration(milliseconds: 50));

    // Bottom sheet contains Open in Payments
    expect(find.text('Open in Payments'), findsOneWidget);
  });
}
