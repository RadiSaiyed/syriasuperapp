# Keep Flutter and plugin entry points, avoid stripping needed classes.
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }
-keep class io.sentry.** { *; }

# Keep generated registrant
-keep class **GeneratedPluginRegistrant { *; }

# Keep OkHttp/okio (some plugins use them)
-dontwarn okhttp3.**
-dontwarn okio.**

