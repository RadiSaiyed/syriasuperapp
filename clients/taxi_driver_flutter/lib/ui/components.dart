import 'package:flutter/material.dart';

class StatusChip extends StatelessWidget {
  final String status;
  const StatusChip({super.key, required this.status});
  Color _color(String s, BuildContext ctx) {
    switch (s) {
      case 'requested':
        return Colors.blueGrey;
      case 'assigned':
        return Colors.indigo;
      case 'accepted':
        return Colors.blue;
      case 'enroute':
        return Colors.orange;
      case 'completed':
        return Colors.green;
      case 'canceled':
        return Colors.red;
      default:
        return Theme.of(ctx).colorScheme.secondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = _color(status, context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: c.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: c.withOpacity(0.4)),
      ),
      child: Text(status, style: TextStyle(color: c, fontWeight: FontWeight.w600)),
    );
  }
}

String friendlyError(Object e) {
  final s = e.toString();
  if (s.contains('user_suspended')) return 'Your account is temporarily suspended.';
  if (s.contains('driver_suspended')) return 'Driver account is suspended.';
  if (s.contains('driver_location_missing')) return 'Please set your location to accept/start.';
  if (s.contains('driver_location_stale')) return 'Location is too old. Update your location.';
  if (s.contains('driver_too_far')) return 'You are too far from the target location.';
  if (s.contains('Too many ride requests')) return 'Too many requests. Please wait a bit.';
  if (s.contains('insufficient_driver_balance')) return 'Insufficient wallet balance to accept. Top up and try again.';
  if (s.contains('insufficient_taxi_wallet_balance')) return 'Taxi wallet balance too low. Top up and try again.';
  if (s.contains('insufficient_rider_balance')) return 'Insufficient rider wallet balance.';
  return s;
}

