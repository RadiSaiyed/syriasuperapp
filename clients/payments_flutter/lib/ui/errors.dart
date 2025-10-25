import 'package:flutter/material.dart';

void showRetrySnack(BuildContext context, String message, VoidCallback onRetry) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
    content: Text(message),
    action: SnackBarAction(label: 'Wiederholen', onPressed: onRetry),
  ));
}

