import 'package:flutter/material.dart';
import 'dart:math' as math;
import 'dart:async';
import 'package:url_launcher/url_launcher.dart';
import 'services.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_ui/shared_ui.dart';
import 'package:shared_ui/message_host.dart';
import 'ui/feedback.dart';
import 'screens/payments_screen.dart';
// Driver UI is now a standalone app (clients/taxi_driver_flutter)
// import 'screens/taxi_driver_screen.dart';
import 'screens/food_screen.dart';
import 'screens/commerce_screen.dart';
import 'screens/utilities_screen.dart';
import 'screens/flights_screen.dart';
import 'screens/bus_screen.dart';
import 'screens/freight_screen.dart';
import 'screens/carmarket_screen.dart';
import 'screens/stays_screen.dart';
import 'screens/doctors_screen.dart';
import 'screens/taxi_screen.dart';
// Chat embedding via Inbox/Chat screens
import 'screens/jobs_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/login_screen.dart';
import 'screens/inbox_screen.dart';
import 'screens/realestate_screen.dart';
import 'screens/agriculture_screen.dart';
import 'screens/livestock_screen.dart';
import 'screens/carrental_screen.dart';
import 'screens/parking_screen.dart';
import 'screens/garages_screen.dart';
import 'screens/ai_gateway_screen.dart';
import 'screens/search_screen.dart';
import 'screens/notifications_screen.dart';
import 'chat_unread.dart';
import 'push_history.dart';
import 'whats_new.dart';
import 'animations.dart';
import 'haptics.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:google_fonts/google_fonts.dart';
// duplicates removed
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'auth.dart';
import 'package:shared_core/shared_core.dart';
import 'screens/outbox_screen.dart';
import 'privacy.dart';
import 'features.dart';
import 'deeplinks.dart';
import 'push_register.dart';

// Align Super‑App buttons with Taxi app button color (SharedColors.lime)
const Color _primaryGlassAccent = Color(0xFFA4FF00);
const Color _warmGlassAccent = Color(0xFFFFB340);
const Color _lightPrimaryText = Color(0xFF1F2933);
const Color _lightSecondaryText = Color(0xFF5B6474);
const Color _lightDisabledText = Color(0xFF9BA4B1);
const Color _darkPrimaryText = Color(0xFFF2F5F8);
const Color _darkSecondaryText = Color(0xFF94A3B8);
const Color _darkDisabledText = Color(0xFF5F6B7A);

// Compile-time flag to optionally bypass login (for demos)
const bool kSkipLogin = bool.fromEnvironment('SKIP_LOGIN', defaultValue: false);

TextTheme _buildTextTheme(Brightness brightness) {
  final base = GoogleFonts.poppinsTextTheme();
  final bool isDark = brightness == Brightness.dark;
  final Color primary = isDark ? _darkPrimaryText : _lightPrimaryText;
  final Color secondary = isDark ? _darkSecondaryText : _lightSecondaryText;
  final Color disabled = isDark ? _darkDisabledText : _lightDisabledText;

  return base
      .copyWith(
        displayLarge: base.displayLarge?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.2),
        displayMedium: base.displayMedium?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.2),
        displaySmall: base.displaySmall?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.15),
        headlineLarge: base.headlineLarge?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.2),
        headlineMedium: base.headlineMedium?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.18),
        headlineSmall: base.headlineSmall?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.16),
        titleLarge: base.titleLarge?.copyWith(
            color: primary, fontWeight: FontWeight.w700, letterSpacing: 0.4),
        titleMedium: base.titleMedium?.copyWith(
            color: primary, fontWeight: FontWeight.w600, letterSpacing: 0.35),
        titleSmall: base.titleSmall?.copyWith(
            color: secondary, fontWeight: FontWeight.w600, letterSpacing: 0.3),
        bodyLarge: base.bodyLarge?.copyWith(
            color: primary, fontWeight: FontWeight.w500, letterSpacing: 0.2),
        bodyMedium: base.bodyMedium?.copyWith(
            color: secondary, fontWeight: FontWeight.w400, letterSpacing: 0.25),
        bodySmall:
            base.bodySmall?.copyWith(color: disabled, letterSpacing: 0.3),
        labelLarge: base.labelLarge?.copyWith(
            color: primary, fontWeight: FontWeight.w700, letterSpacing: 1.0),
        labelMedium: base.labelMedium?.copyWith(
            color: secondary, fontWeight: FontWeight.w600, letterSpacing: 0.8),
        labelSmall: base.labelSmall?.copyWith(
            color: disabled, fontWeight: FontWeight.w600, letterSpacing: 0.6),
      )
      .apply(
          displayColor: primary,
          bodyColor: primary,
          decorationColor: secondary);
}

Future<void> main() async {
  // Create reporter with compile-time settings; defer binding-dependent loads
  final dsnEnv = const String.fromEnvironment('SENTRY_DSN', defaultValue: '');
  final envName = const String.fromEnvironment('APP_ENV', defaultValue: 'dev');
  final release = const String.fromEnvironment('APP_RELEASE', defaultValue: '');
  final reporter = CrashReporter(
    dsn: dsnEnv,
    environment: envName,
    release: release,
  );
  final errorHandler = GlobalErrorHandler(crashReporter: reporter);

  await runWithCrashReporting(
    reporter: reporter,
    appRunner: () async {
      // Perform all operations that may require Flutter bindings in the same zone
      try { await dotenv.load(fileName: ".env"); } catch (_) {}
      await AppTheme.load();
      await AppSettings.load();
      await AppPrivacy.load();
      await FeatureRegistry.load();
      // Optionally disable Sentry at runtime based on privacy
      if (!AppPrivacy.sendCrashReports.value && reporter.isEnabled) {
        await reporter.close();
      }
      errorHandler.install();
      runApp(const SuperApp());
    },
  );
}

class SuperApp extends StatelessWidget {
  const SuperApp({super.key});

  @override
  Widget build(BuildContext context) {
    // removed unused deep link helper

    const seed = Color(0xFF0A84FF);
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: AppTheme.mode,
      builder: (context, themeMode, _) {
        return ValueListenableBuilder<Locale?>(
          valueListenable: AppSettings.locale,
          builder: (context, appLocale, __) {
            final ColorScheme lightColorScheme = ColorScheme.fromSeed(
              seedColor: seed,
              brightness: Brightness.light,
            ).copyWith(
              primary: _primaryGlassAccent,
              secondary: _warmGlassAccent,
              surface: Colors.white.withValues(alpha: 0.12),
              surfaceTint: Colors.white.withValues(alpha: 0.04),
              onPrimary: Colors.black,
              onSecondary: Colors.black,
              outline: Colors.black.withValues(alpha: 0.08),
              outlineVariant: Colors.black.withValues(alpha: 0.12),
            );

            final TextTheme lightTextTheme = _buildTextTheme(Brightness.light);

            final ThemeData lightTheme = ThemeData(
              useMaterial3: true,
              colorScheme: lightColorScheme,
              textTheme: lightTextTheme,
              scaffoldBackgroundColor: Colors.transparent,
              appBarTheme: AppBarTheme(
                backgroundColor: Colors.transparent,
                surfaceTintColor: Colors.transparent,
                elevation: 0,
                centerTitle: true,
                titleTextStyle: lightTextTheme.titleMedium,
                iconTheme: const IconThemeData(color: _lightPrimaryText),
              ),
              dialogTheme: DialogThemeData(
                backgroundColor: Colors.white.withValues(alpha: 0.18),
                surfaceTintColor: Colors.transparent,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18)),
                titleTextStyle: lightTextTheme.titleMedium,
                contentTextStyle: lightTextTheme.bodyMedium,
              ),
              cardTheme: CardThemeData(
                color: Colors.white.withValues(alpha: 0.14),
                surfaceTintColor: Colors.transparent,
                elevation: 0,
                margin: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18)),
              ),
              inputDecorationTheme: InputDecorationTheme(
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide:
                      BorderSide(color: Colors.black.withValues(alpha: 0.08)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide:
                      BorderSide(color: Colors.black.withValues(alpha: 0.08)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide(
                      color: _primaryGlassAccent.withValues(alpha: 0.6)),
                ),
                labelStyle: lightTextTheme.labelMedium,
                hintStyle: lightTextTheme.bodySmall,
              ),
              chipTheme: ChipThemeData(
                backgroundColor: Colors.white.withValues(alpha: 0.18),
                disabledColor: Colors.white.withValues(alpha: 0.08),
                selectedColor: _primaryGlassAccent.withValues(alpha: 0.40),
                secondarySelectedColor:
                    _warmGlassAccent.withValues(alpha: 0.32),
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                labelStyle: lightTextTheme.labelMedium!,
                secondaryLabelStyle: lightTextTheme.labelMedium!
                    .copyWith(color: _lightPrimaryText),
                side: BorderSide(color: Colors.black.withValues(alpha: 0.08)),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
                brightness: Brightness.light,
              ),
              filledButtonTheme: FilledButtonThemeData(
                style: FilledButton.styleFrom(
                  backgroundColor: _primaryGlassAccent,
                  foregroundColor: Colors.black,
                  textStyle: lightTextTheme.labelLarge,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
              ),
              outlinedButtonTheme: OutlinedButtonThemeData(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryGlassAccent,
                  textStyle: lightTextTheme.labelLarge,
                  side: BorderSide(
                      color: _primaryGlassAccent.withValues(alpha: 0.8),
                      width: 1.2),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
              ),
              textButtonTheme: TextButtonThemeData(
                style: TextButton.styleFrom(
                  foregroundColor: _primaryGlassAccent,
                  textStyle: lightTextTheme.labelMedium,
                ),
              ),
              navigationBarTheme: NavigationBarThemeData(
                indicatorColor: _primaryGlassAccent.withValues(alpha: 0.22),
                backgroundColor: Colors.white.withValues(alpha: 0.08),
                elevation: 0,
                height: 74,
                labelTextStyle: WidgetStateProperty.resolveWith((states) {
                  final baseStyle = lightTextTheme.labelMedium!;
                  return states.contains(WidgetState.selected)
                      ? baseStyle.copyWith(color: _lightPrimaryText)
                      : baseStyle.copyWith(color: _lightSecondaryText);
                }),
              ),
              listTileTheme: const ListTileThemeData(
                textColor: _lightPrimaryText,
                iconColor: _lightSecondaryText,
              ),
              bottomSheetTheme: const BottomSheetThemeData(
                backgroundColor: Colors.transparent,
                surfaceTintColor: Colors.transparent,
                elevation: 0,
              ),
              snackBarTheme: SnackBarThemeData(
                backgroundColor: Colors.black.withValues(alpha: 0.70),
                contentTextStyle:
                    lightTextTheme.bodyMedium?.copyWith(color: Colors.white),
                elevation: 0,
                behavior: SnackBarBehavior.floating,
              ),
              pageTransitionsTheme: const PageTransitionsTheme(builders: {
                TargetPlatform.android: CupertinoPageTransitionsBuilder(),
                TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
                TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
                TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
                TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
              }),
            );

            final ThemeData darkBase = SharedTheme.dark();
            final ColorScheme darkColorScheme = darkBase.colorScheme.copyWith(
              primary: _primaryGlassAccent,
              secondary: _warmGlassAccent,
              surface: Colors.white.withValues(alpha: 0.08),
              surfaceTint: Colors.white.withValues(alpha: 0.04),
              onPrimary: Colors.black,
              onSecondary: Colors.black,
              outline: Colors.white.withValues(alpha: 0.10),
              outlineVariant: Colors.white.withValues(alpha: 0.08),
            );
            final TextTheme darkTextTheme = _buildTextTheme(Brightness.dark);

            final ThemeData darkTheme = darkBase.copyWith(
              colorScheme: darkColorScheme,
              scaffoldBackgroundColor: Colors.transparent,
              textTheme: darkTextTheme,
              appBarTheme: darkBase.appBarTheme.copyWith(
                backgroundColor: Colors.transparent,
                surfaceTintColor: Colors.transparent,
                elevation: 0,
                centerTitle: true,
                titleTextStyle: darkTextTheme.titleMedium,
                iconTheme: const IconThemeData(color: _darkSecondaryText),
              ),
              dialogTheme: darkBase.dialogTheme.copyWith(
                backgroundColor: Colors.white.withValues(alpha: 0.10),
                surfaceTintColor: Colors.transparent,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18)),
                titleTextStyle: darkTextTheme.titleMedium,
                contentTextStyle: darkTextTheme.bodyMedium,
              ),
              cardTheme: darkBase.cardTheme.copyWith(
                color: Colors.white.withValues(alpha: 0.12),
                surfaceTintColor: Colors.transparent,
                elevation: 0,
                margin: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20)),
              ),
              chipTheme: darkBase.chipTheme.copyWith(
                backgroundColor: Colors.white.withValues(alpha: 0.10),
                disabledColor: Colors.white.withValues(alpha: 0.06),
                selectedColor: _primaryGlassAccent.withValues(alpha: 0.38),
                secondarySelectedColor:
                    _warmGlassAccent.withValues(alpha: 0.30),
                labelStyle: darkTextTheme.labelMedium!,
                secondaryLabelStyle: darkTextTheme.labelMedium!,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
                side: BorderSide(color: Colors.white.withValues(alpha: 0.10)),
                brightness: Brightness.dark,
              ),
              inputDecorationTheme: darkBase.inputDecorationTheme.copyWith(
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.08),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide:
                      BorderSide(color: Colors.white.withValues(alpha: 0.10)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide:
                      BorderSide(color: Colors.white.withValues(alpha: 0.08)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide(
                      color: _primaryGlassAccent.withValues(alpha: 0.7)),
                ),
                labelStyle: darkTextTheme.labelMedium,
                hintStyle: darkTextTheme.bodySmall,
              ),
              filledButtonTheme: FilledButtonThemeData(
                style: FilledButton.styleFrom(
                  backgroundColor: _primaryGlassAccent,
                  foregroundColor: Colors.black,
                  textStyle: darkTextTheme.labelLarge,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
              ),
              outlinedButtonTheme: OutlinedButtonThemeData(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryGlassAccent,
                  textStyle: darkTextTheme.labelLarge,
                  side: BorderSide(
                      color: _primaryGlassAccent.withValues(alpha: 0.9),
                      width: 1.2),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
              ),
              textButtonTheme: TextButtonThemeData(
                style: TextButton.styleFrom(
                  foregroundColor: _primaryGlassAccent,
                  textStyle: darkTextTheme.labelMedium,
                ),
              ),
              navigationBarTheme: darkBase.navigationBarTheme.copyWith(
                indicatorColor: _primaryGlassAccent.withValues(alpha: 0.26),
                backgroundColor: Colors.white.withValues(alpha: 0.06),
                height: 74,
                labelTextStyle: WidgetStateProperty.resolveWith((states) {
                  final baseStyle = darkTextTheme.labelMedium!;
                  return states.contains(WidgetState.selected)
                      ? baseStyle.copyWith(color: _darkPrimaryText)
                      : baseStyle.copyWith(color: _darkSecondaryText);
                }),
              ),
              listTileTheme: darkBase.listTileTheme.copyWith(
                textColor: _darkPrimaryText,
                iconColor: _darkSecondaryText,
              ),
              bottomSheetTheme: darkBase.bottomSheetTheme.copyWith(
                backgroundColor: Colors.transparent,
                surfaceTintColor: Colors.transparent,
                elevation: 0,
              ),
              snackBarTheme: darkBase.snackBarTheme.copyWith(
                backgroundColor: Colors.black.withValues(alpha: 0.80),
                contentTextStyle:
                    darkTextTheme.bodyMedium?.copyWith(color: Colors.white),
                elevation: 0,
                behavior: SnackBarBehavior.floating,
              ),
              pageTransitionsTheme: const PageTransitionsTheme(builders: {
                TargetPlatform.android: CupertinoPageTransitionsBuilder(),
                TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
                TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
                TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
                TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
              }),
            );

            return MaterialApp(
              title: 'Super‑App',
              themeMode: themeMode,
              locale: appLocale,
              theme: lightTheme,
              darkTheme: darkTheme,
              scaffoldMessengerKey: MessageHost.messengerKey,
              builder: (context, child) => Stack(children: [
                const LiquidBackground(),
                const LiquidGlassOverlay(opacity: 0.30, blur: 60),
                if (child != null) MessageHost(child: child),
              ]),
              routes: {
                '/home': (_) => const HomeScreen(),
                '/login': (_) => const LoginScreen(),
              },
              home: const _RootGate(),
            );
          },
        );
      },
    );
  }
}

class _RootGate extends StatefulWidget {
  const _RootGate();
  @override
  State<_RootGate> createState() => _RootGateState();
}

class _RootGateState extends State<_RootGate> {
  final _store = MultiTokenStore();

  Future<bool> _silentLogin() async {
    if (kSkipLogin) return true;
    // Keep existing token if present and valid; otherwise show login screen.
    final t = await _store.get('payments');
    if (t == null || t.isEmpty) return false;
    final paymentsOk = await validateTokenAndMaybePropagate(
        service: 'payments', propagateAll: true, probePaths: const ['/wallet', '/wallet/transactions']);
    if (paymentsOk) {
      // Opportunistically validate other key vertical tokens; ignore result if missing.
      await validateTokenAndMaybePropagate(
          service: 'chat', propagateAll: false, probePaths: const ['/health']);
      await validateTokenAndMaybePropagate(
          service: 'realestate', propagateAll: false, probePaths: const ['/health']);
    }
    return paymentsOk;
  }

  // Removed unused biometric gate helper and dev-login constants

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _silentLogin(),
      builder: (context, snap) {
        if (!snap.hasData) {
          return const Scaffold(
            body: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 12),
                  Text('Lade…'),
                ],
              ),
            ),
          );
        }
        if (snap.data == true) {
          return const HomeScreen();
        }
        return const LoginScreen();
      },
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;
  @override
  void initState() {
    super.initState();
    DeepLinks.init(context);
    PushRegister.registerIfPossible();
    AppAnimations.load();
    AppHaptics.load();
    ChatUnreadStore.refresh();
    () async {
      final prefs = await SharedPreferences.getInstance();
      final secs = prefs.getInt('chat_unread_interval_secs') ?? 20;
      ChatUnreadStore.start(interval: Duration(seconds: secs.clamp(5, 300)));
    }();
    // Initialize unread badge from push history
    PushHistoryStore.refreshUnread();
    // Present What's New once per version bump
    WidgetsBinding.instance.addPostFrameCallback((_) {
      WhatsNew.maybeShow(context);
    });
  }

  @override
  void dispose() {
    DeepLinks.dispose();
    ChatUnreadStore.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      _AppsGrid(
          onLaunchPayments: () => Navigator.push(context,
              MaterialPageRoute(builder: (_) => const PaymentsScreen())),
          onLaunchTaxi: () async {
            final ok = await ensureLoggedIn(context, service: 'taxi');
            if (!ok || !context.mounted) return;
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const TaxiScreen()),
            );
          }),
      const InboxScreen(),
      const ProfileScreen(),
      const SettingsScreen(),
    ];
    return Scaffold(
      extendBody: true,
      extendBodyBehindAppBar: false,
      appBar: AppBar(
        title: GradientText(
          'SYRIASUPERAPP',
          gradient: LinearGradient(
            colors: [
              Theme.of(context).colorScheme.primary,
              Theme.of(context).colorScheme.secondary,
            ],
          ),
          style: GoogleFonts.poppins(
            fontWeight: FontWeight.w800,
            letterSpacing: 1.4,
            fontSize: 22,
          ),
        ),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
        // No bottom: keep title always fully visible
        actions: [
          const _OutboxButton(),
          IconButton(
            tooltip: 'Notifications',
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen()));
            },
          ),
          IconButton(
            tooltip: 'Search',
            icon: const Icon(Icons.search),
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const SearchScreen()));
            },
          ),
          IconButton(
            tooltip: 'AI Command',
            icon: const Icon(Icons.smart_toy_outlined),
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const AIGatewayScreen()));
            },
          ),
          IconButton(
            icon: const Icon(Icons.wallet),
            onPressed: () async {
              final uri = Uri.parse('payments://');
              if (await canLaunchUrl(uri)) {
                await launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            },
          )
        ],
      ),
      body: _tab == 0 ? Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: Glass(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              child: Row(children: [
                Expanded(child: HapticActionButton(icon: Icons.local_taxi, label: const Text('Ride Now'), onPressed: () {
                  AppHaptics.impact();
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const TaxiScreen()));
                })),
                const SizedBox(width: 8),
                Expanded(child: HapticActionButton(icon: Icons.qr_code_scanner, label: const Text('Scan & Pay'), onPressed: () {
                  AppHaptics.impact();
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const PaymentsScreen(initialAction: 'scan')));
                })),
                const SizedBox(width: 8),
                Expanded(child: HapticActionButton(icon: Icons.add_circle_outline, label: const Text('Top Up'), tonal: true, onPressed: () {
                  AppHaptics.impact();
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const PaymentsScreen(initialAction: 'topup')));
                })),
              ]),
            ),
          ),
        ),
        Expanded(child: pages[_tab]),
      ]) : pages[_tab],
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Glass(
              child: Row(children: [
                Expanded(
                    child: HapticActionButton(
                        icon: Icons.qr_code_scanner,
                        label: const Text('Scan & Pay'),
                        onPressed: () {
                          Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const PaymentsScreen(
                                        initialAction: 'scan',
                                      )));
                        })),
                const SizedBox(width: 8),
                Expanded(
                    child: HapticActionButton(
                        icon: Icons.swap_horiz,
                        label: const Text('P2P'),
                        tonal: true,
                        onPressed: () {
                          Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const PaymentsScreen(
                                        view: 'p2p',
                                      )));
                        })),
                const SizedBox(width: 8),
                Expanded(
                    child: HapticActionButton(
                        icon: Icons.add_circle_outline,
                        label: const Text('Top Up'),
                        tonal: true,
                        onPressed: () {
                          Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const PaymentsScreen(
                                        initialAction: 'topup',
                                      )));
                        })),
              ]),
            ),
            const SizedBox(height: 8),
            Glass(
              padding: EdgeInsets.zero,
              child: ValueListenableBuilder<int>(
                valueListenable: PushHistoryStore.unread,
                builder: (context, unread, _) {
                  return NavigationBar(
                    selectedIndex: _tab,
                    destinations: [
                      const NavigationDestination(icon: Icon(Icons.apps), label: 'Apps'),
                      ValueListenableBuilder<int>(
                        valueListenable: ChatUnreadStore.count,
                        builder: (context, chatUnread, __) {
                          final total = unread + (chatUnread > 0 ? chatUnread : 0);
                          Widget icon() {
                            final base = const Icon(Icons.notifications_none);
                            if (total <= 0) return base;
                            return Stack(clipBehavior: Clip.none, children: [base, Positioned(right: -2, top: -2, child: Container(padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1), decoration: BoxDecoration(color: Colors.redAccent, borderRadius: BorderRadius.circular(10)), child: Text(total > 99 ? '99+' : '$total', style: const TextStyle(color: Colors.white, fontSize: 9))))]);
                          }
                          return NavigationDestination(icon: icon(), label: 'Inbox');
                        },
                      ),
                      const NavigationDestination(icon: Icon(Icons.person_outline), label: 'Profile'),
                      const NavigationDestination(icon: Icon(Icons.settings_outlined), label: 'Settings'),
                    ],
                    onDestinationSelected: (i) {
                      if (i == 1) { ChatUnreadStore.set(0); PushHistoryStore.setSeenNow(); }
                      setState(() => _tab = i);
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Taxi tile now launches the standalone taxi module (see TaxiModule.build)

class _AppsGrid extends StatefulWidget {
  final FutureOr<void> Function() onLaunchPayments;
  final FutureOr<void> Function() onLaunchTaxi;
  const _AppsGrid({required this.onLaunchPayments, required this.onLaunchTaxi});

  @override
  State<_AppsGrid> createState() => _AppsGridState();
}

class _AppsGridState extends State<_AppsGrid> {
  final PageController _pageCtrl = PageController();
  int _page = 0;
  void _onFeaturesChanged() { if (mounted) setState(() {}); }

  @override
  void initState() {
    super.initState();
    FeatureRegistry.enabled.addListener(_onFeaturesChanged);
  }

  @override
  void dispose() {
    FeatureRegistry.enabled.removeListener(_onFeaturesChanged);
    _pageCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    Color c(String title) {
      switch (title) {
        case 'Payments':
          return CategoryColors.payments;
        case 'Bus':
          return CategoryColors.taxi;
        case 'Freight':
          return CategoryColors.freight;
        case 'Taxi':
          return CategoryColors.taxi;
        case 'Flights':
          return CategoryColors.flights;
        case 'Jobs':
          return CategoryColors.jobs;
        case 'Doctors':
          return CategoryColors.doctors;
        case 'Food':
          return CategoryColors.food;
        case 'Stays':
          return CategoryColors.stays;
        case 'Chat':
          return CategoryColors.chat;
        case 'Commerce':
          return CategoryColors.commerce;
        case 'Utilities':
          return CategoryColors.utilities;
        case 'Real Estate':
          return CategoryColors.realestate;
        case 'Car Market':
          return CategoryColors.carmarket;
      }
      return SharedColors.textSecondary;
    }

    final List<Widget> cards = [];
    bool vis(String id) => FeatureRegistry.isEnabled(id);
    void maybe(String id, Widget card) { if (vis(id)) cards.add(card); }

    // Page 1 (6 items)
    maybe('payments', _AppCard(
        customIcon: const Text('💳', style: TextStyle(fontSize: 44)),
        title: 'Payments',
        accent: c('Payments'),
        onTap: widget.onLaunchPayments));
    maybe('taxi', _AppCard(
        customIcon: const Text('🚕', style: TextStyle(fontSize: 44)),
        title: 'Taxi',
        accent: c('Taxi'),
        onTap: widget.onLaunchTaxi));
    maybe('food', _AppCard(
        customIcon: const Text('🍔', style: TextStyle(fontSize: 44)),
        title: 'Food',
        accent: c('Food'),
        onTap: () => Navigator.push(
            context, MaterialPageRoute(builder: (_) => const FoodScreen()))));
    maybe('flights', _AppCard(
        customIcon: const Text('✈️', style: TextStyle(fontSize: 44)),
        title: 'Flights',
        accent: c('Flights'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const FlightsScreen()))));
    maybe('bus', _AppCard(
        customIcon: const Text('🚌', style: TextStyle(fontSize: 44)),
        title: 'Bus',
        accent: c('Bus'),
        onTap: () => Navigator.push(
            context, MaterialPageRoute(builder: (_) => const BusScreen()))));
    maybe('chat', _AppCard(
        customIcon: const Text('💬', style: TextStyle(fontSize: 44)),
        title: 'Chat',
        accent: c('Chat'),
        onTap: () => Navigator.push(
            context, MaterialPageRoute(builder: (_) => const InboxScreen()))));

    // Page 2 (requested order)
    maybe('carmarket', _AppCard(
        customIcon: const Text('🚗', style: TextStyle(fontSize: 44)),
        title: 'Car Market',
        accent: c('Car Market'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const CarMarketScreen()))));
    maybe('freight', _AppCard(
        customIcon: const Text('🚛', style: TextStyle(fontSize: 44)),
        title: 'Freight',
        accent: c('Freight'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const FreightScreen()))));
    maybe('carrental', _AppCard(
        customIcon: const Text('🔑🚗', style: TextStyle(fontSize: 44)),
        title: 'Car Rental',
        accent: c('Car Market'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const CarRentalScreen()))));
    maybe('stays', _AppCard(
        customIcon: const Text('🏨', style: TextStyle(fontSize: 44)),
        title: 'Stays',
        accent: c('Stays'),
        onTap: () => Navigator.push(
            context, MaterialPageRoute(builder: (_) => const StaysScreen()))));
    maybe('realestate', _AppCard(
        customIcon: const Text('🏠', style: TextStyle(fontSize: 44)),
        title: 'Real Estate',
        accent: c('Real Estate'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const RealEstateScreen()))));
    maybe('jobs', _AppCard(
        customIcon: const Text('💼', style: TextStyle(fontSize: 44)),
        title: 'Jobs',
        accent: c('Jobs'),
        onTap: () => Navigator.push(
            context, MaterialPageRoute(builder: (_) => const JobsScreen()))));

    // Page 3 (remaining)
    maybe('utilities', _AppCard(
        customIcon: const Text('🔌', style: TextStyle(fontSize: 44)),
        title: 'Utilities',
        accent: c('Utilities'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const UtilitiesScreen()))));
    maybe('doctors', _AppCard(
        customIcon: const Text('🩺', style: TextStyle(fontSize: 44)),
        title: 'Doctors',
        accent: c('Doctors'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const DoctorsScreen()))));
    maybe('commerce', _AppCard(
        customIcon: const Text('🛍️', style: TextStyle(fontSize: 44)),
        title: 'Commerce',
        accent: c('Commerce'),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const CommerceScreen()))));
    maybe('parking', _AppCard(
        customIcon: const Text('🅿️', style: TextStyle(fontSize: 44)),
        title: 'Parking',
        accent: const Color(0xFF7BD881),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const ParkingScreen()))));
    maybe('garages', _AppCard(
        customIcon: const Text('🏢', style: TextStyle(fontSize: 44)),
        title: 'Garages',
        accent: const Color(0xFF84A7FF),
        onTap: () {
          Navigator.push(context,
              MaterialPageRoute(builder: (_) => const GaragesScreen()));
        }));
    maybe('agriculture', _AppCard(
        customIcon: const Text('🫒🍅', style: TextStyle(fontSize: 44)),
        title: 'Agriculture',
        accent: SharedColors.lime,
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const AgricultureScreen()))));
    maybe('ai', _AppCard(
        customIcon: const Text('🤖', style: TextStyle(fontSize: 44)),
        title: 'AI Assistant',
        accent: const Color(0xFF64D2FF),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const AIGatewayScreen()))));
    maybe('livestock', _AppCard(
        customIcon: const Text('🐄', style: TextStyle(fontSize: 56)),
        iconSize: 48,
        title: 'Livestock',
        accent: const Color(0xFFFFE08A),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const LivestockScreen()))));
    // Chunk into pages of exactly 6 apps each
    const int perPage = 6;
    final List<List<Widget>> pages = [];
    for (int start = 0; start < cards.length; start += perPage) {
      final end = math.min(start + perPage, cards.length);
      pages.add(cards.sublist(start, end));
    }

    final int pageCount = pages.length;
    return Column(
      children: [
        Expanded(
          child: MediaQuery.removePadding(
            context: context,
            removeTop: true,
            child: PageView.builder(
              controller: _pageCtrl,
              onPageChanged: (i) => setState(() => _page = i),
              itemCount: pageCount,
              itemBuilder: (context, index) {
                final items = pages[index];
                final width = MediaQuery.of(context).size.width;
                final cross = width < 480 ? 2 : 3;
                return GridView.count(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                  crossAxisCount: cross,
                  mainAxisSpacing: 0,
                  crossAxisSpacing: 4,
                  childAspectRatio: 1.25,
                  children: items.isEmpty ? const [SizedBox()] : items,
                );
              },
            ),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List.generate(pageCount, (i) {
            final bool active = i == _page;
            return AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
              width: active ? 8 : 6,
              height: active ? 8 : 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: active
                    ? Theme.of(context).colorScheme.primary
                    : Colors.white.withValues(alpha: 0.35),
              ),
            );
          }),
        ),
      ],
    );
  }
}

class _OutboxButton extends StatefulWidget {
  const _OutboxButton();
  @override
  State<_OutboxButton> createState() => _OutboxButtonState();
}

class _OutboxButtonState extends State<_OutboxButton> {
  int _count = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _refresh());
  }

  Future<void> _refresh() async {
    try {
      int total = 0;
      for (final svc in ServiceConfig.services) {
        final q = OfflineRequestQueue(svc);
        final items = await q.load();
        total += items.length;
      }
      if (mounted) setState(() => _count = total);
    } catch (_) {}
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        IconButton(
          tooltip: 'Ausstehende Vorgänge',
          icon: const Icon(Icons.outbox_outlined),
          onPressed: () {
            Navigator.push(context, MaterialPageRoute(builder: (_) => const OutboxScreen()));
          },
        ),
        if (_count > 0)
          Positioned(
            right: 8,
            top: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: Colors.redAccent,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text('$_count', style: const TextStyle(color: Colors.white, fontSize: 10)),
            ),
          ),
      ],
    );
  }
}

class _AppCard extends StatelessWidget {
  final Widget? customIcon;
  final String title;
  final FutureOr<void> Function() onTap;
  final Color? accent;
  final double? iconSize;
  const _AppCard(
      {this.customIcon,
      required this.title,
      required this.onTap,
      this.accent,
      this.iconSize});

  @override
  Widget build(BuildContext context) {
    final double iconSize = this.iconSize ?? 36.0;
    final Widget baseIcon = customIcon ??
        Icon(Icons.apps,
            size: iconSize,
            color: accent ?? Theme.of(context).colorScheme.primary);
    return GlassCard(
      child: Semantics(
        label: title,
        button: true,
        onTap: () {},
        child: InkWell(
          onTap: () async => await onTap(),
          child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (accent != null)
                Container(
                    height: 3,
                    width: double.infinity,
                    decoration: BoxDecoration(
                        color: accent, borderRadius: BorderRadius.circular(2))),
              SizedBox(
                height: iconSize + 4,
                width: iconSize + 4,
                child: Center(
                  child: FittedBox(fit: BoxFit.scaleDown, child: baseIcon),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                title,
                textAlign: TextAlign.center,
                maxLines: 2,
                softWrap: true,
                overflow: TextOverflow.fade,
              ),
            ],
          ),
        ),
        ),
      ),
    );
  }
}

// Removed unused _PinnedHeaderDelegate

class GradientText extends StatelessWidget {
  final String text;
  final TextStyle? style;
  final Gradient gradient;
  const GradientText(this.text,
      {super.key, this.style, required this.gradient});

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (bounds) {
        return gradient.createShader(
          Rect.fromLTWH(0, 0, bounds.width, bounds.height),
        );
      },
      child: Text(
        text,
        style: (style ?? const TextStyle()).copyWith(color: Colors.white),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}

class AppTheme {
  static const _prefKey = 'app_theme_mode';
  static final ValueNotifier<ThemeMode> mode = ValueNotifier(ThemeMode.system);

  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final s = prefs.getString(_prefKey);
      if (s == 'light') {
        mode.value = ThemeMode.light;
      } else if (s == 'dark') {
        mode.value = ThemeMode.dark;
      } else {
        mode.value = ThemeMode.dark; // default: Dark
      }
    } catch (_) {
      mode.value = ThemeMode.dark;
    }
  }

  static Future<void> setMode(ThemeMode m) async {
    mode.value = m;
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = m == ThemeMode.light
          ? 'light'
          : m == ThemeMode.dark
              ? 'dark'
              : 'system';
      await prefs.setString(_prefKey, v);
    } catch (_) {}
  }
}

class AppSettings {
  static const _langKey = 'app_language'; // 'system' | 'en' | 'de' | 'ar'
  static const _flowKey = 'map_traffic';
  static const _liteKey = 'lite_mode_enabled';
  static final ValueNotifier<Locale?> locale = ValueNotifier<Locale?>(null);
  static final ValueNotifier<bool> showTrafficFlow = ValueNotifier<bool>(
      const bool.fromEnvironment('MAPS_SHOW_TRAFFIC', defaultValue: true));
  static final ValueNotifier<bool> liteMode = ValueNotifier<bool>(false);

  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final lang = prefs.getString(_langKey) ?? 'system';
      locale.value = _localeFrom(lang);
      showTrafficFlow.value = prefs.getBool(_flowKey) ??
          const bool.fromEnvironment('MAPS_SHOW_TRAFFIC', defaultValue: true);
      liteMode.value = prefs.getBool(_liteKey) ?? false;
    } catch (_) {}
  }

  static Locale? _localeFrom(String code) {
    switch (code) {
      case 'en':
        return const Locale('en');
      case 'de':
        return const Locale('de');
      case 'ar':
        return const Locale('ar');
      case 'ku':
        return const Locale('ku');
      default:
        return null; // system
    }
  }

  static Future<void> setLanguage(String code) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_langKey, code);
      locale.value = _localeFrom(code);
    } catch (_) {}
  }

  static Future<void> setTrafficFlow(bool v) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_flowKey, v);
      showTrafficFlow.value = v;
    } catch (_) {}
  }

  static Future<void> setTrafficIncidents(bool v) async {
    // No-op: incidents overlay not used in Google Maps setup
  }

  static Future<void> setLiteMode(bool v) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_liteKey, v);
      liteMode.value = v;
    } catch (_) {}
  }
}

// Legacy map bootstrap removed; using Google/OSM paths only.
