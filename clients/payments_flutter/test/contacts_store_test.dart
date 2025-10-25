import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:payments_flutter/contacts_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('ContactsStore add/load', () async {
    SharedPreferences.setMockInitialValues({});
    final store = ContactsStore();
    await store.add('Ali', '+963900000001');
    await store.add('Omar', '+963900000002');
    final list = await store.load();
    expect(list.length, 2);
    expect(list[0]['name'], isNotEmpty);
  });
}

