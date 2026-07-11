package com.pandahis.histomap.common.util;

/** 历史年份展示：公元前用 -XX。 */
public final class HistoryYearFormat {

  private HistoryYearFormat() {}

  public static String label(int year) {
    if (year < 0) {
      return "-" + Math.abs(year);
    }
    return String.valueOf(year);
  }
}
