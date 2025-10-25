import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:payments_flutter/api.dart';

/// Starts a tiny local HTTP server that simulates transient failures (502)
/// followed by success, and captures the Idempotency-Key header.
Future<void> main() async {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Retry & Idempotency', () {
    late HttpServer server;
    late Uri base;
    final seenIdem = <String>[];
    setUpAll(() async {
      server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      base = Uri.parse('http://127.0.0.1:${server.port}');
      int payLinkCount = 0;
      int walletCount = 0;
      server.listen((HttpRequest req) async {
        final path = req.uri.path;
        if (path == '/payments/links/pay' && req.method == 'POST') {
          // Capture Idempotency-Key across retries
          final idem = req.headers.value('idempotency-key') ?? '';
          seenIdem.add(idem);
          payLinkCount++;
          if (payLinkCount == 1) {
            req.response.statusCode = 502;
            await req.response.close();
            return;
          }
          req.response.statusCode = 200;
          req.response.headers.contentType = ContentType.json;
          req.response.write(jsonEncode({'ok': true, 'amount_cents': 1234}));
          await req.response.close();
          return;
        }
        if (path == '/wallet' && req.method == 'GET') {
          walletCount++;
          if (walletCount == 1) {
            req.response.statusCode = 503;
            await req.response.close();
            return;
          }
          req.response.statusCode = 200;
          req.response.headers.contentType = ContentType.json;
          req.response.write(jsonEncode({'wallet': {'balance_cents': 0, 'currency_code': 'SYP'}, 'user': {}}));
          await req.response.close();
          return;
        }
        // Default 404
        req.response.statusCode = 404;
        await req.response.close();
      });
    });

    tearDownAll(() async {
      await server.close(force: true);
    });

    testWidgets('idempotent POST retries and preserves Idempotency-Key', (tester) async {
      final api = ApiClient(baseUrl: base.toString(), tokenStore: TokenStore());
      final key = 'test-idem-123';
      final res = await api.payLink(code: 'abc', idempotencyKey: key, amountCents: 1234);
      expect(res['ok'], true);
      // First 502 + second 200 => exactly two attempts
      expect(seenIdem.length, greaterThanOrEqualTo(2));
      // All seen keys should equal our provided key
      for (final k in seenIdem) {
        expect(k, key);
      }
    });

    testWidgets('GET retries on 503', (tester) async {
      final api = ApiClient(baseUrl: base.toString(), tokenStore: TokenStore());
      final w = await api.getWallet();
      expect(w['wallet']?['currency_code'], 'SYP');
    });
  });
}

