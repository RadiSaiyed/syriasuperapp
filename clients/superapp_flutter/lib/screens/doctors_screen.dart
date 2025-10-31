import 'package:flutter/material.dart';
import '../services.dart';
import 'package:shared_core/shared_core.dart';
import 'package:shared_ui/message_host.dart';
import '../animations.dart';
import 'package:shared_ui/glass.dart';

class _SkeletonTile extends StatelessWidget {
  const _SkeletonTile();
  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Container(width: 36, height: 36, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(18))),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(height: 12, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(4))),
            const SizedBox(height: 6),
            Container(height: 10, width: 120, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(4))),
          ])),
        ]),
      ),
    );
  }
}

class DoctorsScreen extends StatefulWidget {
  const DoctorsScreen({super.key});
  @override
  State<DoctorsScreen> createState() => _DoctorsScreenState();
}

class _DoctorsScreenState extends State<DoctorsScreen> {
  String _health = '?';
  bool _loading = false;
  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson(
        'doctors',
        '/health',
        options: const RequestOptions(cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Doctors')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          FilledButton(onPressed: _loading ? null : _healthCheck, child: const Text('Health')),
          const SizedBox(height: 8),
          AnimatedSwitcher(
            duration: AppAnimations.switcherDuration,
            child: _loading
                ? Column(key: const ValueKey('skel'), children: List.generate(3, (i) => const _SkeletonTile()))
                : GlassCard(key: const ValueKey('status'), child: ListTile(title: const Text('Status'), subtitle: Text(_health))),
          ),
        ]),
      ),
    );
  }
}
