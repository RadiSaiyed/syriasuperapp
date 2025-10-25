import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:chat_flutter/api.dart';
import 'package:chat_flutter/screens/contacts_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8091', tokenStore: TokenStore(), deviceStore: DeviceStore());
  @override
  Future<List<Map<String, dynamic>>> listContacts() async => [{'user_id':'u2','phone':'+963900000002','name':'User B'}];
}

void main() {
  testWidgets('Contacts list renders', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ContactsScreen(api: api))));
    await tester.pump();
    expect(find.text('User B'), findsOneWidget);
  });
}

