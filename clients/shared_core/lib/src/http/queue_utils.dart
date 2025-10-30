import 'shared_http_client.dart';
import 'request_options.dart';
import 'offline_queue.dart';
import 'offline_history.dart';
import '../errors/core_error.dart';

/// Flushes queued offline requests for the given [client]'s service.
/// Applies the same semantics as the client's internal auto-flush: non-retriable
/// errors drop the item; retriable errors stop the flush and keep remaining items.
Future<void> flushOfflineQueue(SharedHttpClient client) async {
  final queue = OfflineRequestQueue(client.service);
  final history = OfflineQueueHistoryStore();
  final items = await queue.load();
  if (items.isEmpty) return;
  final remaining = <OfflineQueuedRequest>[];
  for (final it in items) {
    try {
      await client.send(CoreHttpRequest(
        method: it.method,
        path: it.path,
        body: it.bodyText,
        options: RequestOptions(
          queryParameters: it.query,
          idempotent: true,
          idempotencyKey: it.idempotencyKey,
          attachAuthHeader: true,
          expectValidationErrors: it.expectValidationErrors,
          headers: it.contentType == null ? null : {'Content-Type': it.contentType!},
        ),
      ));
      await history.appendFromQueued(client.service, it, 'sent');
    } catch (e) {
      if (e is CoreError && !e.isRetriable) {
        // drop and record removal
        await history.appendFromQueued(client.service, it, 'removed');
      } else {
        remaining.add(it);
        break;
      }
    }
  }
  if (remaining.length != items.length) {
    await queue.save(remaining);
  }
}
