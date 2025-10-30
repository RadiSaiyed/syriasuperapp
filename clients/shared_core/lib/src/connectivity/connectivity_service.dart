import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// High-level connectivity status abstraction used across clients.
enum ConnectivityStatus { online, offline }

class ConnectivityService {
  ConnectivityService({Connectivity? connectivity})
      : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  Future<ConnectivityStatus> checkStatus() async {
    final result = await _connectivity.checkConnectivity();
    return result == ConnectivityResult.none
        ? ConnectivityStatus.offline
        : ConnectivityStatus.online;
  }

  Stream<ConnectivityStatus> get onStatusChange => _connectivity
      .onConnectivityChanged
      .map((event) => event == ConnectivityResult.none ? ConnectivityStatus.offline : ConnectivityStatus.online)
      .distinct();
}
