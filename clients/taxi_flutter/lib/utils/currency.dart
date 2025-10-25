import 'package:intl/intl.dart';

final NumberFormat _sypNumberFormat = NumberFormat.decimalPattern();

String formatSyp(dynamic amount) {
  num? value;
  if (amount == null) {
    value = null;
  } else if (amount is num) {
    value = amount;
  } else {
    value = num.tryParse(amount.toString());
  }
  if (value == null) {
    return 'SYP -';
  }
  return '${_sypNumberFormat.format(value)} SYP';
}
