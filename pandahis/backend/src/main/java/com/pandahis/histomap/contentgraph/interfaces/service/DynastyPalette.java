package com.pandahis.histomap.contentgraph.interfaces.service;

/**
 * 视觉规范 v2.0 · 朝代 6 色循环（卡片 accent / 边条）
 */
public final class DynastyPalette {
  private static final String[] ACCENT = {
      "#84572F", "#F1A805", "#F2D6A1", "#92ADA4", "#B3D9E0", "#EDD5C0"
  };

  private static final String[][] RULES = {
      {"秦汉", "秦", "汉", "西汉", "东汉", "清", "清朝", "清代"},
      {"三国", "魏晋", "南北朝", "魏", "蜀", "吴", "晋", "东晋", "西晋", "南朝", "北朝"},
      {"隋", "唐", "五代", "隋唐", "武周", "后梁", "后唐", "后晋", "后汉", "后周"},
      {"宋", "北宋", "南宋", "辽", "金", "西夏"},
      {"元", "蒙古", "元朝"},
      {"先秦", "夏", "商", "周", "春秋", "战国", "明", "明朝", "明代"}
  };

  private DynastyPalette() {}

  public static String resolveAccentHex(String dynastyName, String eraName) {
    int idx = toneIndex(dynastyName, eraName);
    return ACCENT[idx];
  }

  static int toneIndex(String dynastyName, String eraName) {
    String raw = ((dynastyName == null ? "" : dynastyName) + " " + (eraName == null ? "" : eraName)).trim();
    if (raw.isEmpty()) {
      return 0;
    }
    for (int i = 0; i < RULES.length; i++) {
      for (String p : RULES[i]) {
        if (raw.contains(p)) {
          return i;
        }
      }
    }
    return 0;
  }
}
