
class RhythmaDateUtils {
  RhythmaDateUtils._();

  static String toDateKey(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  static bool isSameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  static bool isToday(DateTime date) => isSameDay(date, DateTime.now());

  static bool isSameMonth(DateTime date, DateTime month) =>
      date.year == month.year && date.month == month.month;

  static int daysInMonth(DateTime month) =>
      DateTime(month.year, month.month + 1, 0).day;
}
