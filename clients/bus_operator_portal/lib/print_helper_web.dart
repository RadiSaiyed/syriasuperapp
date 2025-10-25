// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

void triggerPrint() {
  try {
    html.window.print();
  } catch (_) {}
}

