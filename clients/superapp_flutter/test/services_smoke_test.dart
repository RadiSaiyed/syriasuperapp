import 'package:flutter_test/flutter_test.dart';
import 'package:superapp_flutter/services.dart';

void main() {
  group('ServiceConfig helpers', () {
    test('baseUrl returns localhost defaults', () {
      expect(ServiceConfig.baseUrl('payments'), 'http://localhost:8080');
      expect(ServiceConfig.baseUrl('chat'), 'http://localhost:8091');
    });

    test('endpoint appends path segments safely', () {
      expect(
        ServiceConfig.endpoint('realestate', '/health').toString(),
        'http://localhost:8092/health',
      );
      expect(
        ServiceConfig.endpoint('commerce', 'shops').toString(),
        'http://localhost:8083/shops',
      );
    });
  });
}
