import 'package:flutter/material.dart';
import 'package:chat_flutter/api.dart' as chat_api;
import 'package:chat_flutter/main.dart' as chat_app;

import '../services.dart';

class ChatModule {
  const ChatModule._();

  static Widget build() {
    final base = ServiceConfig.baseUrl('chat');
    return chat_app.App(
      initialBaseUrl: base,
      tokenStore: _SuperAppChatTokenStore(MultiTokenStore()),
      deviceStore: chat_api.DeviceStore(),
    );
  }
}

class _SuperAppChatTokenStore extends chat_api.TokenStore {
  final MultiTokenStore multiStore;
  _SuperAppChatTokenStore(this.multiStore);

  @override
  Future<String?> getToken() => getTokenFor('chat', store: multiStore);

  @override
  Future<void> setToken(String token) => multiStore.set('chat', token);

  @override
  Future<void> clear() => multiStore.clear('chat');
}
