import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  static final tabs = [
    _Tab('/wallet', Icons.account_balance_wallet, 'Wallet'),
    _Tab('/merchant', Icons.qr_code, 'Merchant'),
    _Tab('/vouchers', Icons.card_giftcard, 'Vouchers'),
    _Tab('/admin', Icons.admin_panel_settings, 'Admin'),
    _Tab('/links', Icons.link, 'Links'),
    _Tab('/subs', Icons.repeat, 'Subs'),
  ];

  int _indexForLocation(BuildContext context) {
    final l = GoRouterState.of(context).uri.toString();
    final i = tabs.indexWhere((t) => l.startsWith(t.path));
    return i < 0 ? 0 : i;
  }

  @override
  Widget build(BuildContext context) {
    final idx = _indexForLocation(context);
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: idx,
        destinations: [ for (final t in tabs) NavigationDestination(icon: Icon(t.icon), label: t.label) ],
        onDestinationSelected: (i) => context.go(tabs[i].path),
      ),
    );
  }
}

class _Tab { final String path; final IconData icon; final String label; const _Tab(this.path, this.icon, this.label); }
