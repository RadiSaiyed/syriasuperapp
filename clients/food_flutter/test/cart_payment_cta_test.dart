import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:food_flutter/api.dart';
import 'package:food_flutter/screens/cart_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8090', tokenStore: TokenStore());

  @override
  Future<Map<String, dynamic>> getCart() async => {
    'id': 'c1',
    'items': [
      {'id':'i1','menu_item_id':'m1','name':'Shawarma','price_cents':15000,'qty':1,'subtotal_cents':15000},
    ],
    'total_cents': 15000,
  };

  @override
  Future<Map<String, dynamic>> checkout() async => {
    'id':'o1','status':'created','restaurant_id':'r1','total_cents':15000,'delivery_address':null,'created_at':'2025-01-01T00:00:00Z','payment_request_id':'req-123','items':[]
  };

  @override
  Future<Map<String, dynamic>> updateCartItem({required String itemId, required int qty}) async => await getCart();
  @override
  Future<Map<String, dynamic>> deleteCartItem({required String itemId}) async => await getCart();
}

void main() {
  testWidgets('Checkout shows Open in Payments CTA', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: CartScreen(api: api))));
    await tester.pump();
    expect(find.text('Checkout'), findsOneWidget);
    await tester.tap(find.text('Checkout'));
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Open in Payments'), findsOneWidget);
  });
}

