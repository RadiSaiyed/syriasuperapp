import 'package:flutter/material.dart';

class SharedMessages {
  static Locale _locale(BuildContext context) =>
      WidgetsBinding.instance.platformDispatcher.locale;

  static String loginFirst(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Bitte zuerst anmelden';
      case 'ar':
        return 'يرجى تسجيل الدخول أولاً';
      default:
        return 'Login first';
    }
  }

  // Generic UI
  static String cancel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Abbrechen';
      case 'ar':
        return 'إلغاء';
      default:
        return 'Cancel';
    }
  }

  static String save(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Speichern';
      case 'ar':
        return 'حفظ';
      default:
        return 'Save';
    }
  }

  static String create(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Erstellen';
      case 'ar':
        return 'إنشاء';
      default:
        return 'Create';
    }
  }

  static String networkOffline(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Offline – Verbindung prüfen';
      case 'ar':
        return 'دون اتصال - تحقق من الشبكة';
      default:
        return 'Offline – check your connection';
    }
  }

  static String requestTimedOut(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Zeitüberschreitung – später erneut versuchen';
      case 'ar':
        return 'انتهت مهلة الطلب، حاول لاحقاً';
      default:
        return 'Request timed out – try again';
    }
  }

  static String sessionExpired(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Sitzung abgelaufen – bitte erneut anmelden';
      case 'ar':
        return 'انتهت الجلسة، يرجى تسجيل الدخول مرة أخرى';
      default:
        return 'Session expired – please sign in again';
    }
  }

  static String relogin(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Erneut anmelden';
      case 'ar':
        return 'تسجيل الدخول';
      default:
        return 'Re-login';
    }
  }

  static String accessDenied(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Zugriff verweigert';
      case 'ar':
        return 'تم رفض الوصول';
      default:
        return 'Access denied';
    }
  }

  static String resourceMissing(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Element nicht gefunden';
      case 'ar':
        return 'العنصر غير موجود';
      default:
        return 'Item not found';
    }
  }

  static String validationError(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Eingabe prüfen';
      case 'ar':
        return 'تحقق من البيانات';
      default:
        return 'Check the input';
    }
  }

  static String conflictError(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Konflikt – Seite aktualisieren';
      case 'ar':
        return 'تعارض - حدِّث الصفحة';
      default:
        return 'Conflict – refresh';
    }
  }

  static String rateLimited(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Zu viele Anfragen – kurz warten';
      case 'ar':
        return 'طلبات كثيرة - يرجى الانتظار';
      default:
        return 'Too many requests – wait a moment';
    }
  }

  static String serverError(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Serverfehler – bitte später nochmal';
      case 'ar':
        return 'خطأ في الخادم - حاول لاحقاً';
      default:
        return 'Server error – please retry later';
    }
  }

  static String requestCancelled(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Anfrage abgebrochen';
      case 'ar':
        return 'تم إلغاء الطلب';
      default:
        return 'Request cancelled';
    }
  }

  static String unexpectedError(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Unerwarteter Fehler';
      case 'ar':
        return 'خطأ غير متوقع';
      default:
        return 'Unexpected error';
    }
  }

  static String clone(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Klonen';
      case 'ar':
        return 'استنساخ';
      default:
        return 'Clone';
    }
  }

  static String close(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Schließen';
      case 'ar':
        return 'إغلاق';
      default:
        return 'Close';
    }
  }

  static String active(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Aktiv';
      case 'ar':
        return 'نشط';
      default:
        return 'Active';
    }
  }

  static String branch(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Filiale';
      case 'ar':
        return 'فرع';
      default:
        return 'Branch';
    }
  }

  static String none(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Keine';
      case 'ar':
        return 'لا يوجد';
      default:
        return 'None';
    }
  }

  static String filter(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Filter:';
      case 'ar':
        return 'تصفية:';
      default:
        return 'Filter:';
    }
  }

  static String all(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Alle';
      case 'ar':
        return 'الكل';
      default:
        return 'All';
    }
  }

  static String reserved(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Reserviert';
      case 'ar':
        return 'محجوز';
      default:
        return 'Reserved';
    }
  }

  static String confirmed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Bestätigt';
      case 'ar':
        return 'مؤكد';
      default:
        return 'Confirmed';
    }
  }

  static String canceledLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Storniert';
      case 'ar':
        return 'ملغي';
      default:
        return 'Canceled';
    }
  }

  static String phoneContains(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Telefon enthält';
      case 'ar':
        return 'يحتوي الهاتف';
      default:
        return 'Phone contains';
    }
  }

  // Portal titles
  static String portalLoginTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Operator‑Portal Login';
      case 'ar':
        return 'تسجيل دخول بوابة المشغل';
      default:
        return 'Operator Portal Login';
    }
  }

  static String sendOtp(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'OTP senden';
      case 'ar':
        return 'إرسال رمز التحقق';
      default:
        return 'Send OTP';
    }
  }

  static String login(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Anmelden';
      case 'ar':
        return 'تسجيل الدخول';
      default:
        return 'Login';
    }
  }

  static String noOperatorMembership(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Keine Betreiber‑Mitgliedschaft gefunden.';
      case 'ar':
        return 'لم يتم العثور على عضوية مشغل.';
      default:
        return 'No operator membership found.';
    }
  }

  static String createOperator(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Operator erstellen';
      case 'ar':
        return 'إنشاء مشغل';
      default:
        return 'Create Operator';
    }
  }

  static String createOperatorDev(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Operator erstellen (DEV)';
      case 'ar':
        return 'إنشاء مشغل (DEV)';
      default:
        return 'Create Operator (DEV)';
    }
  }

  static String seatMapTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Sitzplan';
      case 'ar':
        return 'خريطة المقاعد';
      default:
        return 'Seat Map';
    }
  }

  static String editTripTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Fahrt bearbeiten';
      case 'ar':
        return 'تعديل الرحلة';
      default:
        return 'Edit Trip';
    }
  }

  static String vehicleLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Fahrzeug:';
      case 'ar':
        return 'المركبة:';
      default:
        return 'Vehicle:';
    }
  }

  static String manifestTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Manifest';
      case 'ar':
        return 'بيان الركاب';
      default:
        return 'Manifest';
    }
  }

  static String kioskScanTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Kiosk‑Scan';
      case 'ar':
        return 'مسح الكشك';
      default:
        return 'Kiosk Scan';
    }
  }

  static String printManifestTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Manifest drucken';
      case 'ar':
        return 'طباعة البيان';
      default:
        return 'Print Manifest';
    }
  }

  static String dailyTotalsTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Tägliche Summen';
      case 'ar':
        return 'الإجماليات اليومية';
      default:
        return 'Daily Totals';
    }
  }

  static String byBranchTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Nach Filiale';
      case 'ar':
        return 'حسب الفرع';
      default:
        return 'By Branch';
    }
  }

  static String recent(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Letzte';
      case 'ar':
        return 'الأحدث';
      default:
        return 'Recent';
    }
  }

  static String markBoarded(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Einstieg markieren';
      case 'ar':
        return 'وضع علامة تم الصعود';
      default:
        return 'Mark boarded';
    }
  }

  static String computeLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Berechnen';
      case 'ar':
        return 'احسب';
      default:
        return 'Compute';
    }
  }

  static String apiBaseUrlTitle(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'API‑Basis‑URL';
      case 'ar':
        return 'عنوان الأساس لواجهة API';
      default:
        return 'API Base URL';
    }
  }

  static String cancelled(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Abgebrochen';
      case 'ar':
        return 'أُلغي';
      default:
        return 'Canceled';
    }
  }

  // Generic failures
  static String loadFailed(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Laden fehlgeschlagen';
      case 'ar':
        return 'فشل التحميل';
      default:
        return 'Load failed';
    }
  }

  static String walletRefreshFailed(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Wallet-Aktualisierung fehlgeschlagen';
      case 'ar':
        return 'فشل تحديث المحفظة';
      default:
        return 'Wallet refresh failed';
    }
  }

  // Success/info
  static String scheduled(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Geplant';
      case 'ar':
        return 'تمت الجدولة';
      default:
        return 'Scheduled';
    }
  }

  static String requestedPaid(BuildContext context, String rideId) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Angefordert & bezahlt. Fahrt: $rideId';
      case 'ar':
        return 'تم الطلب والدفع. الرحلة: $rideId';
      default:
        return 'Requested & paid. Ride: $rideId';
    }
  }

  static String requestedCash(BuildContext context, String rideId) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Angefordert (Bar). Fahrt: $rideId';
      case 'ar':
        return 'تم الطلب (نقداً). الرحلة: $rideId';
      default:
        return 'Requested (cash). Ride: $rideId';
    }
  }

  static String contactsPermissionDenied(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Kontakte-Berechtigung verweigert';
      case 'ar':
        return 'تم رفض إذن جهات الاتصال';
      default:
        return 'Contacts permission denied';
    }
  }

  static String contactPickFailed(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Kontaktwahl fehlgeschlagen';
      case 'ar':
        return 'فشل اختيار جهة الاتصال';
      default:
        return 'Contact pick failed';
    }
  }

  static String ratingFailed(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Bewertung fehlgeschlagen';
      case 'ar':
        return 'فشل التقييم';
      default:
        return 'Rating failed';
    }
  }

  static String cloneDone(BuildContext context) {
    final code = _locale(context).languageCode.toLowerCase();
    switch (code) {
      case 'de':
        return 'Klonen abgeschlossen';
      case 'ar':
        return 'تم الاستنساخ';
      default:
        return 'Clone done';
    }
  }

  // Common labels
  static String addLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Hinzufügen';
      case 'ar':
        return 'إضافة';
      default:
        return 'Add';
    }
  }

  static String loadLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Laden';
      case 'ar':
        return 'تحميل';
      default:
        return 'Load';
    }
  }

  static String exportCsvLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'CSV exportieren';
      case 'ar':
        return 'تصدير CSV';
      default:
        return 'Export CSV';
    }
  }

  static String exportBranchesCsvLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Filial‑CSV exportieren';
      case 'ar':
        return 'تصدير CSV للفروع';
      default:
        return 'Export Branches CSV';
    }
  }

  static String scanLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Scannen';
      case 'ar':
        return 'مسح';
      default:
        return 'Scan';
    }
  }

  static String kioskLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Kiosk';
      case 'ar':
        return 'نظام كشك';
      default:
        return 'Kiosk';
    }
  }

  static String checkLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Prüfen';
      case 'ar':
        return 'تحقق';
      default:
        return 'Check';
    }
  }

  static String fromLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Von';
      case 'ar':
        return 'من';
      default:
        return 'From';
    }
  }

  static String toLabel(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Bis';
      case 'ar':
        return 'إلى';
      default:
        return 'To';
    }
  }

  // Admin/portal common
  static String createFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Erstellung fehlgeschlagen';
      case 'ar':
        return 'فشلت عملية الإنشاء';
      default:
        return 'Create failed';
    }
  }

  static String deleteFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Löschen fehlgeschlagen';
      case 'ar':
        return 'فشلت عملية الحذف';
      default:
        return 'Delete failed';
    }
  }

  static String toggleFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Umschalten fehlgeschlagen';
      case 'ar':
        return 'فشل التبديل';
      default:
        return 'Toggle failed';
    }
  }

  static String exportFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Export fehlgeschlagen';
      case 'ar':
        return 'فشل التصدير';
      default:
        return 'Export failed';
    }
  }

  static String csvExportFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'CSV‑Export fehlgeschlagen';
      case 'ar':
        return 'فشل تصدير CSV';
      default:
        return 'CSV export failed';
    }
  }

  static String branchesCsvFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Filial‑CSV fehlgeschlagen';
      case 'ar':
        return 'فشل تصدير CSV للفروع';
      default:
        return 'Branches CSV failed';
    }
  }

  static String scanFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Scan fehlgeschlagen';
      case 'ar':
        return 'فشل المسح';
      default:
        return 'Scan failed';
    }
  }

  static String boardedMarked(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Einstieg markiert';
      case 'ar':
        return 'تم تعليم الصعود';
      default:
        return 'Boarded marked';
    }
  }

  static String offlineQueued(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Offline in Warteschlange';
      case 'ar':
        return 'تمت إضافته إلى قائمة الانتظار دون اتصال';
      default:
        return 'Offline queued';
    }
  }

  static String addFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Hinzufügen fehlgeschlagen';
      case 'ar':
        return 'فشل الإضافة';
      default:
        return 'Add failed';
    }
  }

  static String roleChangeFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Rollenänderung fehlgeschlagen';
      case 'ar':
        return 'فشل تغيير الدور';
      default:
        return 'Role change failed';
    }
  }

  static String setBranchFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Zweig zuweisen fehlgeschlagen';
      case 'ar':
        return 'فشل تعيين الفرع';
      default:
        return 'Set branch failed';
    }
  }

  static String removeFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Entfernen fehlgeschlagen';
      case 'ar':
        return 'فشل الإزالة';
      default:
        return 'Remove failed';
    }
  }

  static String loadSeatsFailed(BuildContext context) {
    switch (_locale(context).languageCode.toLowerCase()) {
      case 'de':
        return 'Sitzplätze laden fehlgeschlagen';
      case 'ar':
        return 'فشل تحميل المقاعد';
      default:
        return 'Failed to load seats';
    }
  }
}
