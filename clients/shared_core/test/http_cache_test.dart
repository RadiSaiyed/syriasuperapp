import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/shared_core.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('HttpCache stores and retrieves within TTL', () async {
    SharedPreferences.setMockInitialValues({});
    final cache = HttpCache(namespace: 'test');
    const key = 'https://example.com/items?q=1';
    await cache.set(key, '{"ok":true}', const Duration(milliseconds: 200));
    final v1 = await cache.get(key);
    expect(v1, '{"ok":true}');
    await Future<void>.delayed(const Duration(milliseconds: 250));
    final v2 = await cache.get(key);
    expect(v2, isNull);
  });
}

