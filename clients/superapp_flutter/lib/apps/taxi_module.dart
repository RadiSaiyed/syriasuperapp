import 'package:flutter/material.dart';
import 'dart:async';
import 'package:taxi_flutter/api.dart' as taxi_api;
import 'package:taxi_flutter/main.dart' as taxi_app;

import '../services.dart';

class TaxiModule {
  const TaxiModule._();

  static Widget build({VoidCallback? onRequestLogin}) {
    final base = ServiceConfig.baseUrl('taxi');
    return taxi_app.App(
      initialBaseUrl: base,
      tokenStore: _SuperAppTaxiTokenStore(MultiTokenStore()),
      loginPlaceholderBuilder: (ctx) => _SuperAppTaxiLoginPlaceholder(
        onRequestLogin: onRequestLogin,
      ),
    );
  }
}

class _SuperAppTaxiTokenStore extends taxi_api.TokenStore {
  final MultiTokenStore multiStore;
  _SuperAppTaxiTokenStore(this.multiStore);

  @override
  Future<String?> getToken() => getTokenFor('taxi', store: multiStore);

  @override
  Future<void> setToken(String token) => multiStore.set('taxi', token);

  @override
  Future<void> clear() => multiStore.clear('taxi');
}

class _SuperAppTaxiLoginPlaceholder extends StatelessWidget {
  final VoidCallback? onRequestLogin;
  const _SuperAppTaxiLoginPlaceholder({this.onRequestLogin});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Card(
          color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.3),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.lock_outline, size: 48),
                const SizedBox(height: 16),
                const Text(
                  'Bitte zuerst im SuperApp-Profil anmelden, um Taxi nutzen zu können.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  alignment: WrapAlignment.center,
                  children: [
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      child: const Text('Schließen'),
                    ),
                    FilledButton.icon(
                      onPressed: () {
                        Navigator.of(context).maybePop();
                        if (onRequestLogin != null) {
                          Future.microtask(onRequestLogin!);
                        }
                      },
                      icon: const Icon(Icons.person),
                      label: const Text('Zum Profil'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
