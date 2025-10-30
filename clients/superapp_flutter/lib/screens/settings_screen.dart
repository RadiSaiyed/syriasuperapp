import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../privacy.dart';
import '../whats_new.dart';
import '../animations.dart';
import '../chat_unread.dart';
// Removed debug imports

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  ThemeMode _theme = AppTheme.mode.value;
  bool _bioEnabled = false;
  String _lang = 'system';
  bool _flow = false;
  bool _lite = false;
  bool _crash = false;
  bool _analytics = false;
  bool _loading = true;
  int _chatInterval = 20;
  AnimMode _anim = AnimMode.normal;
  bool _haptic = true;
  bool _sound = false;

  @override
  void initState() {
    super.initState();
    _loadPrefs();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    var savedLang = (prefs.getString('app_language') ?? 'system');
    // Coerce disabled languages back to system
    if (savedLang == 'de' || savedLang == 'ku') {
      await AppSettings.setLanguage('system');
      savedLang = 'system';
    }
    setState(() {
      _theme = AppTheme.mode.value;
      _bioEnabled = prefs.getBool('biometric_enabled') ?? false;
      _lang = savedLang;
      _flow = AppSettings.showTrafficFlow.value;
      _lite = AppSettings.liteMode.value;
      _crash = AppPrivacy.sendCrashReports.value;
      _analytics = AppPrivacy.sendAnalytics.value;
      _chatInterval = prefs.getInt('chat_unread_interval_secs') ?? 20;
      final am = prefs.getString('anim_mode') ?? 'normal';
      _anim = am == 'off' ? AnimMode.off : am == 'smooth' ? AnimMode.smooth : AnimMode.normal;
      _haptic = prefs.getBool('haptic_enabled') ?? true;
      _sound = prefs.getBool('sound_enabled') ?? false;
      _loading = false;
    });
  }

  Future<void> _setTheme(ThemeMode m) async {
    await AppTheme.setMode(m);
    setState(() => _theme = m);
  }

  Future<void> _setBiometric(bool v) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('biometric_enabled', v);
    setState(() => _bioEnabled = v);
  }

  // Radio tiles replaced by compact dropdowns

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(16), children: [
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Appearance', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      DropdownMenu<ThemeMode>(
                        initialSelection: _theme,
                        onSelected: (v) => _setTheme(v ?? ThemeMode.system),
                        dropdownMenuEntries: const [
                          DropdownMenuEntry(value: ThemeMode.system, label: 'Use system setting'),
                          DropdownMenuEntry(value: ThemeMode.light, label: 'Light'),
                          DropdownMenuEntry(value: ThemeMode.dark, label: 'Dark'),
                        ],
                      ),
                      const SizedBox(height: 12),
                      const Text('Animations', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      DropdownMenu<AnimMode>(
                        initialSelection: _anim,
                        onSelected: (v) async {
                          final next = v ?? AnimMode.normal;
                          setState(() => _anim = next);
                          await AppAnimations.setMode(next);
                        },
                        dropdownMenuEntries: const [
                          DropdownMenuEntry(value: AnimMode.off, label: 'Off'),
                          DropdownMenuEntry(value: AnimMode.normal, label: 'Normal'),
                          DropdownMenuEntry(value: AnimMode.smooth, label: 'Smooth'),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Privacy', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      SwitchListTile(
                        title: const Text('Send crash reports (opt‑in)'),
                        subtitle: const Text('Helps us improve stability. No PII sent.'),
                        value: _crash,
                        onChanged: (v) async {
                          setState(() => _crash = v);
                          await AppPrivacy.setCrashReports(v);
                        },
                      ),
                      SwitchListTile(
                        title: const Text('Send usage analytics (beta, opt‑in)'),
                        value: _analytics,
                        onChanged: (v) async {
                          setState(() => _analytics = v);
                          await AppPrivacy.setAnalytics(v);
                        },
                      ),
                      const Divider(),
                      const Text('Feedback', style: TextStyle(fontWeight: FontWeight.w600)),
                      SwitchListTile(
                        title: const Text('Haptics for actions'),
                        value: _haptic,
                        onChanged: (v) async {
                          setState(() => _haptic = v);
                          await AppHaptics.setHaptic(v);
                        },
                      ),
                      SwitchListTile(
                        title: const Text('Sound for notifications'),
                        value: _sound,
                        onChanged: (v) async {
                          setState(() => _sound = v);
                          await AppHaptics.setSound(v);
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Language', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      DropdownMenu<String>(
                        initialSelection: _lang,
                        onSelected: (v) {
                          final next = v ?? 'system';
                          if (next == 'de' || next == 'ku') return; // disabled
                          setState(() => _lang = next);
                          AppSettings.setLanguage(next);
                        },
                        dropdownMenuEntries: const [
                          DropdownMenuEntry(value: 'system', label: 'Use system'),
                          DropdownMenuEntry(value: 'en', label: 'English'),
                          DropdownMenuEntry(value: 'de', label: 'Deutsch', enabled: false),
                          DropdownMenuEntry(value: 'ar', label: 'العربية'),
                          DropdownMenuEntry(value: 'ku', label: 'Kurdî', enabled: false),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('Chat Unread Refresh', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    DropdownMenu<int>(
                      initialSelection: _chatInterval,
                      onSelected: (v) async {
                        final secs = (v ?? 20).clamp(5, 300);
                        setState(() => _chatInterval = secs);
                        final prefs = await SharedPreferences.getInstance();
                        await prefs.setInt('chat_unread_interval_secs', secs);
                        ChatUnreadStore.start(interval: Duration(seconds: secs));
                      },
                      dropdownMenuEntries: const [
                        DropdownMenuEntry(value: 10, label: '10 seconds'),
                        DropdownMenuEntry(value: 20, label: '20 seconds'),
                        DropdownMenuEntry(value: 60, label: '60 seconds'),
                      ],
                    ),
                  ]),
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: SwitchListTile(
                  title: const Text('Enable Biometrics (Face ID / Touch ID)'),
                  value: _bioEnabled,
                  onChanged: _setBiometric,
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: ListTile(
                  title: const Text("Show What's New again"),
                  subtitle: const Text('Zeigt den Hinweis beim nächsten Start erneut.'),
                  trailing: OutlinedButton(
                    onPressed: () async {
                      final prefs = await SharedPreferences.getInstance();
                      await prefs.setBool('whats_new_v2_shown', false);
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Will show on next app start")));
                    },
                    child: const Text('Reset'),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text('Map Overlays',
                          style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      SwitchListTile(
                        title: const Text('Show traffic flow'),
                        value: _flow,
                        onChanged: (v) {
                          setState(() => _flow = v);
                          AppSettings.setTrafficFlow(v);
                        },
                      ),
                      const SizedBox(height: 4),
                      const Text('Note: May apply when maps reload.'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Glass(
                child: SwitchListTile(
                  title: const Text('Lite Mode (Data Saver)'),
                  subtitle: const Text('Reduziert Datenverbrauch, deaktiviert Prefetching'),
                  value: _lite,
                  onChanged: (v) async {
                    setState(() => _lite = v);
                    await AppSettings.setLiteMode(v);
                  },
                ),
              ),
              // Debug panel removed per request
            ]),
    );
  }
}
