// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitleRider => 'راكب تاكسي';
  @override
  String get appTitleDriver => 'سائق تاكسي';

  @override
  String get navRider => 'راكب';
  @override
  String get navDriver => 'سائق';

  @override
  String get openPayments => 'فتح المدفوعات';

  @override
  String get setBaseUrl => 'تعيين عنوان الخادم';

  @override
  String get save => 'حفظ';

  @override
  String get cancel => 'إلغاء';

  @override
  String get tapSets => 'النقر يحدد:';

  @override
  String get pickup => 'الانطلاق';

  @override
  String get dropoff => 'الوصول';

  @override
  String get quote => 'تسعير';

  @override
  String get requestRide => 'طلب رحلة';

  @override
  String get myRides => 'رحلاتي';

  @override
  String get lastRide => 'آخر رحلة:';

  @override
  String get status => 'الحالة:';

  @override
  String get applyDev => 'تفعيل (تجريبي)';

  @override
  String get setLoc => 'تعيين الموقع';

  @override
  String get profileEarnings => 'الملف / الأرباح';

  @override
  String get topup => 'شحن الرصيد';
  @override
  String get accept => 'قبول';
  @override
  String get start => 'بدء';
  @override
  String get complete => 'إنهاء';

  @override
  String fareQuoted(Object cents) {
    return 'الأجرة (تقديري): $cents سنت';
  }

  @override
  String fareFinal(Object cents) {
    return 'الأجرة (نهائي): $cents سنت';
  }

  @override
  String get rideCanceled => 'تم إلغاء الرحلة';
  @override
  String get driverEnabled => 'تم تفعيل السائق';
  @override
  String get driverInfoLoaded => 'تم تحميل معلومات السائق';

  @override
  String get paymentsNotAvailable => 'تطبيق المدفوعات غير متوفر';

  @override
  String get actions => 'إجراءات';

  @override
  String get rideCompleted => 'تم إنهاء الرحلة';

  @override
  String get cashPlease => 'يرجى الدفع نقداً. شكراً!';

  @override
  String priceOfRide({required Object cents}) {
    return 'سعر الرحلة: $centsس (نقداً)';
  }

  @override
  String eta(Object mins) {
    return 'الوصول ~ $mins دقيقة';
  }

  @override
  String get rateFive => 'تقييم 5★';

  @override
  String get chooseTaxiClass => 'اختر فئة التاكسي';
  @override
  String get rideClassStandard => 'عادي';
  @override
  String get rideClassComfort => 'مريح';
  @override
  String get rideClassYellow => 'الأصفر';
  @override
  String get rideClassVIP => 'VIP';
  @override
  String get rideClassVAN => 'فان';
  @override
  String get rideClassElectro => 'كهربائي';

  @override
  String get cancelRide => 'إلغاء الرحلة';

  @override
  String get schedule15m => 'جدولة (15د)';

  @override
  String get dispatchDev => 'تشغيل (تجريبي)';

  @override
  String get optionalStopPromo => 'توقف اختياري ورمز ترويجي';

  @override
  String get stopLatOptional => 'إحداثي توقف (اختياري)';

  @override
  String get stopLonOptional => 'إحداثي توقف (اختياري)';

  @override
  String get promoCodeOptional => 'رمز ترويجي (اختياري)';

  @override
  String get favorites => 'المفضلة';

  @override
  String get saveCurrentPickup => 'حفظ نقطة الانطلاق الحالية';

  @override
  String get setPickup => 'تعيين الانطلاق';

  @override
  String get setDrop => 'تعيين الوصول';

  @override
  String get continueLabel => 'متابعة';

  @override
  String scheduledAt(Object ts) {
    return 'تمت الجدولة عند $ts';
  }

  @override
  String get dispatchRequested => 'تم طلب التنفيذ (تجريبي)';

  @override
  String get searchAddress => 'ابحث عن عنوان';

  @override
  String get typeAnAddress => 'اكتب عنوانًا';

  @override
  String get close => 'إغلاق';
}
