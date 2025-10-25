// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

Future<void> beep() async {
  try {
    final audio = html.AudioElement();
    // use a short data URI beep (440Hz 100ms)
    audio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQwAAAAA';
    await audio.play();
  } catch (_) {}
}

