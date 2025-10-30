import 'package:flutter/material.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';

/// Simple, reusable dev OTP login component.
///
/// Shows a phone TextField by default and a submit button. On submit, calls
/// [onLogin] with the entered phone. If it completes successfully, invokes
/// [onLoggedIn].
class DevOtpLogin extends StatefulWidget {
  final Future<void> Function(String phone) onLogin;
  final VoidCallback onLoggedIn;
  final String label;
  final double? maxWidth;
  final bool showPhoneField;
  final String initialPhone;

  const DevOtpLogin({
    super.key,
    required this.onLogin,
    required this.onLoggedIn,
    this.label = 'Request OTP',
    this.maxWidth,
    this.showPhoneField = true,
    this.initialPhone = '+963900000001',
  });

  @override
  State<DevOtpLogin> createState() => _DevOtpLoginState();
}

class _DevOtpLoginState extends State<DevOtpLogin> {
  bool _loading = false;
  late final TextEditingController _phoneCtrl = TextEditingController(text: widget.initialPhone);

  Future<void> _handleLogin() async {
    setState(() => _loading = true);
    try {
      final phone = widget.showPhoneField ? _phoneCtrl.text.trim() : widget.initialPhone;
      await widget.onLogin(phone);
      if (!mounted) return;
      widget.onLoggedIn();
    } catch (e) {
      if (!mounted) return;
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    if (widget.showPhoneField) {
      children.addAll([
        TextField(
          controller: _phoneCtrl,
          decoration: const InputDecoration(labelText: 'Phone'),
          keyboardType: TextInputType.phone,
          enabled: !_loading,
        ),
        const SizedBox(height: 12),
      ]);
    }
    children.add(FilledButton(
      onPressed: _loading ? null : _handleLogin,
      child: Text(widget.label),
    ));

    final content = Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.stretch, children: children);
    final wrapped = widget.maxWidth == null
        ? content
        : ConstrainedBox(constraints: BoxConstraints(maxWidth: widget.maxWidth!), child: content);
    return Center(child: wrapped);
  }
}

/// Dev OTP login with phone + optional name field.
class DevOtpLoginWithName extends StatefulWidget {
  final Future<void> Function(String phone, String? name) onLogin;
  final VoidCallback onLoggedIn;
  final String label;
  final double? maxWidth;
  final String initialPhone;
  final String nameLabel;
  final bool nameRequired;

  const DevOtpLoginWithName({
    super.key,
    required this.onLogin,
    required this.onLoggedIn,
    this.label = 'Request OTP',
    this.maxWidth,
    this.initialPhone = '+963900000001',
    this.nameLabel = 'Name (optional)',
    this.nameRequired = false,
  });

  @override
  State<DevOtpLoginWithName> createState() => _DevOtpLoginWithNameState();
}

class _DevOtpLoginWithNameState extends State<DevOtpLoginWithName> {
  bool _loading = false;
  late final TextEditingController _phoneCtrl = TextEditingController(text: widget.initialPhone);
  final TextEditingController _nameCtrl = TextEditingController();

  Future<void> _handleLogin() async {
    final phone = _phoneCtrl.text.trim();
    final name = _nameCtrl.text.trim();
    if (widget.nameRequired && name.isEmpty) { MessageHost.showInfoBanner(context, 'Enter your name'); return; }
    setState(() => _loading = true);
    try {
      await widget.onLogin(phone, name.isEmpty ? null : name);
      if (!mounted) return;
      widget.onLoggedIn();
    } catch (e) {
      if (!mounted) return;
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[
      TextField(
        controller: _phoneCtrl,
        decoration: const InputDecoration(labelText: 'Phone'),
        keyboardType: TextInputType.phone,
        enabled: !_loading,
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _nameCtrl,
        decoration: InputDecoration(labelText: widget.nameLabel),
        textInputAction: TextInputAction.done,
        enabled: !_loading,
        onSubmitted: (_) => _loading ? null : _handleLogin(),
      ),
      const SizedBox(height: 12),
      FilledButton(onPressed: _loading ? null : _handleLogin, child: Text(widget.label)),
    ];
    final content = Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.stretch, children: children);
    final wrapped = widget.maxWidth == null
        ? content
        : ConstrainedBox(constraints: BoxConstraints(maxWidth: widget.maxWidth!), child: content);
    return Center(child: wrapped);
  }
}
