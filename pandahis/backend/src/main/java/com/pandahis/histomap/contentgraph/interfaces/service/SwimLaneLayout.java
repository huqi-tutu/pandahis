package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** 泳道条目布局（对齐 miniapp/小程序 mock-dynasty.js：rpx 虚线 + 文字自适应胶囊） */
final class SwimLaneLayout {
  record SwimBarInput(String boxId, String title, int start, int end, String priority) {}
  private static final int SHEET_RPX = 1440;
  private static final int CONTINUOUS_CHAR_W = 20;
  private static final int CONTINUOUS_PAD_RPX = 24;
  private static final int CONTINUOUS_MIN_CHIP = 56;
  private static final int CONTINUOUS_MIN_GAP_RPX = 20;

  private static final int SHICHEN_APPEAR_MIN = 10;
  private static final int SHICHEN_APPEAR_MAX = 20;
  private static final int SHICHEN_CHIP_RPX = 120;

  private static final int ISOLATED_CHAR_W = 20;
  private static final int ISOLATED_PAD_RPX = 24;
  private static final int ISOLATED_MIN_CHIP = 56;
  private static final int ISOLATED_MIN_GAP_RPX = 16;

  private SwimLaneLayout() {}

  static List<List<UnitSwimMatrixDTO.Bar>> packContinuous(
      List<SwimBarInput> bars,
      int startYear,
      int span
  ) {
    List<SwimBarInput> sorted = new ArrayList<>(bars);
    sorted.sort(Comparator.comparingInt(b -> b.start()));

    List<Double> rowEnds = new ArrayList<>();
    List<PlacedContinuous> placed = new ArrayList<>();
    double gapYears = (CONTINUOUS_MIN_GAP_RPX / (double) SHEET_RPX) * span;

    for (SwimBarInput bar : sorted) {
      double chipW = calcContinuousChipWidth(bar.title());
      double minUnitRpx = chipW + 16;
      double minSpanYears = (minUnitRpx / SHEET_RPX) * span;
      double effectiveEnd = Math.max(bar.end(), bar.start() + minSpanYears);

      int assigned = -1;
      for (int r = 0; r < rowEnds.size(); r++) {
        if (rowEnds.get(r) + gapYears <= bar.start()) {
          assigned = r;
          rowEnds.set(r, effectiveEnd);
          break;
        }
      }
      if (assigned == -1) {
        assigned = rowEnds.size();
        rowEnds.add(effectiveEnd);
      }

      double unitLeftPct = pctYear(bar.start(), startYear, span);
      double unitWidthPct = pctSpan(bar.start(), effectiveEnd, startYear, span);
      double unitWidthRpx = unitWidthPct / 100.0 * SHEET_RPX;

      double maxLeftPct = 100 - (chipW / SHEET_RPX * 100);
      if (unitLeftPct > maxLeftPct) {
        unitLeftPct = maxLeftPct;
        unitWidthPct = 100 - unitLeftPct;
        unitWidthRpx = unitWidthPct / 100.0 * SHEET_RPX;
      }

      double chipLeftRpx = Math.max(0, (unitWidthRpx - chipW) / 2);
      double lineLeftW = chipLeftRpx;
      double lineRightL = chipLeftRpx + chipW;
      double lineRightW = Math.max(0, unitWidthRpx - lineRightL);

      placed.add(new PlacedContinuous(
          bar,
          assigned,
          unitLeftPct,
          unitWidthPct,
          chipLeftRpx,
          chipW,
          lineLeftW,
          lineRightL,
          lineRightW
      ));
    }

    return rowsFromContinuous(placed, startYear, span);
  }

  static List<List<UnitSwimMatrixDTO.Bar>> packShichen(
      List<SwimBarInput> bars,
      int startYear,
      int span
  ) {
    List<ShichenNorm> normalized = bars.stream()
        .map(ShichenNorm::from)
        .sorted(Comparator.comparingInt((ShichenNorm b) -> b.birth).thenComparingInt(b -> b.death))
        .toList();

    List<Integer> rowEnds = new ArrayList<>();
    List<PlacedShichen> placed = new ArrayList<>();

    for (ShichenNorm bar : normalized) {
      int assigned = -1;
      for (int r = 0; r < rowEnds.size(); r++) {
        if (rowEnds.get(r) <= bar.birth) {
          assigned = r;
          rowEnds.set(r, bar.death);
          break;
        }
      }
      if (assigned == -1) {
        assigned = rowEnds.size();
        rowEnds.add(bar.death);
      }
      placed.add(new PlacedShichen(bar.input, layoutShichen(bar, startYear, span), assigned));
    }

    int maxRow = placed.stream().mapToInt(p -> p.row).max().orElse(-1);
    List<List<UnitSwimMatrixDTO.Bar>> rows = new ArrayList<>();
    for (int r = 0; r <= maxRow; r++) {
      rows.add(new ArrayList<>());
    }
    for (PlacedShichen p : placed) {
      rows.get(p.row).add(p.bar);
    }
    for (int r = 0; r < rows.size(); r++) {
      List<UnitSwimMatrixDTO.Bar> row = rows.get(r);
      row.sort(Comparator.comparing(b -> parsePct(b.unitLeft())));
      for (int i = 0; i < row.size(); i++) {
        UnitSwimMatrixDTO.Bar old = row.get(i);
        row.set(i, withZIndex(old, 10 + i));
      }
    }
    return rows.isEmpty() ? List.of(List.of()) : rows;
  }

  static List<List<UnitSwimMatrixDTO.Bar>> packIsolated(
      List<SwimBarInput> bars,
      int startYear,
      int span
  ) {
    List<SwimBarInput> sorted = new ArrayList<>(bars);
    sorted.sort(Comparator.comparingInt(b -> b.start()));

    List<Double> rowEnds = new ArrayList<>();
    List<PlacedIsolated> placed = new ArrayList<>();
    double gapYears = (ISOLATED_MIN_GAP_RPX / (double) SHEET_RPX) * span;

    for (SwimBarInput bar : sorted) {
      double chipRpx = Math.max(ISOLATED_MIN_CHIP, bar.title().length() * ISOLATED_CHAR_W + ISOLATED_PAD_RPX);
      double chipPct = chipRpx / SHEET_RPX * 100;
      double mid = (bar.start() + bar.end()) / 2.0;
      double chipHalfYears = (chipRpx / 2.0 / SHEET_RPX) * span;
      double chipLeftYear = mid - chipHalfYears;
      double chipRightYear = mid + chipHalfYears;

      int assigned = -1;
      for (int r = 0; r < rowEnds.size(); r++) {
        if (rowEnds.get(r) + gapYears <= chipLeftYear) {
          assigned = r;
          rowEnds.set(r, chipRightYear);
          break;
        }
      }
      if (assigned == -1) {
        assigned = rowEnds.size();
        rowEnds.add(chipRightYear);
      }

      double left = pctYear(chipLeftYear, startYear, span);
      left = Math.max(0, Math.min(100 - chipPct, left));

      placed.add(new PlacedIsolated(bar, assigned, left, chipPct));
    }

    int maxRow = placed.stream().mapToInt(p -> p.row).max().orElse(-1);
    List<List<UnitSwimMatrixDTO.Bar>> rows = new ArrayList<>();
    for (int r = 0; r <= maxRow; r++) {
      rows.add(new ArrayList<>());
    }
    for (PlacedIsolated p : placed) {
      rows.get(p.row).add(toIsolatedBar(p.input, p.leftPct, p.widthPct, startYear, span));
    }
    return rows.isEmpty() ? List.of(List.of()) : rows;
  }

  private static List<List<UnitSwimMatrixDTO.Bar>> rowsFromContinuous(
      List<PlacedContinuous> placed,
      int startYear,
      int span
  ) {
    int maxRow = placed.stream().mapToInt(p -> p.row).max().orElse(-1);
    List<List<UnitSwimMatrixDTO.Bar>> rows = new ArrayList<>();
    for (int r = 0; r <= maxRow; r++) {
      rows.add(new ArrayList<>());
    }
    for (PlacedContinuous p : placed) {
      rows.get(p.row).add(toContinuousBar(p, startYear, span));
    }
    for (List<UnitSwimMatrixDTO.Bar> row : rows) {
      row.sort(Comparator.comparing(b -> parsePct(b.unitLeft())));
      for (int i = 0; i < row.size(); i++) {
        row.set(i, withZIndex(row.get(i), 10 + i));
      }
    }
    return rows.isEmpty() ? List.of(List.of()) : rows;
  }

  private static UnitSwimMatrixDTO.Bar toContinuousBar(
      PlacedContinuous p,
      int startYear,
      int span
  ) {
    SwimBarInput b = p.bar;
    String timeRange = fmtYear(b.start()) + " — " + fmtYear(b.end());
    String unitLeft = fmtPct(p.unitLeftPct);
    String unitWidth = fmtPct(p.unitWidthPct);
    return new UnitSwimMatrixDTO.Bar(
        b.title(),
        b.boxId(),
        b.boxId(),
        b.title(),
        unitLeft,
        unitWidth,
        unitLeft,
        unitWidth,
        fmtRpx(p.chipLeftRpx),
        fmtRpx(p.chipWRpx),
        fmtRpx(p.lineLeftW),
        fmtRpx(p.lineRightL),
        fmtRpx(p.lineRightW),
        b.priority(),
        "default",
        10,
        timeRange
    );
  }

  private static UnitSwimMatrixDTO.Bar layoutShichen(
      ShichenNorm bar,
      int startYear,
      int span
  ) {
    int lifeYears = Math.max(bar.death - bar.birth, 1);
    double unitLeftPct = pctYear(bar.birth, startYear, span);
    double unitWidthPct = Math.max(lifeYears / (double) span * 100, 1.2);
    double unitWidthRpx = lifeYears / (double) span * SHEET_RPX;

    double appearMid = (bar.appearStart + bar.appearEnd) / 2.0;
    double chipCenterRpx = ((appearMid - bar.birth) / lifeYears) * unitWidthRpx;
    double chipLeftRpx = chipCenterRpx - SHICHEN_CHIP_RPX / 2.0;
    chipLeftRpx = Math.max(0, Math.min(Math.max(0, unitWidthRpx - SHICHEN_CHIP_RPX), chipLeftRpx));

    double lineLeftRpx = chipLeftRpx;
    double lineRightLft = chipLeftRpx + SHICHEN_CHIP_RPX;
    double lineRightRpx = Math.max(0, unitWidthRpx - lineRightLft);

    SwimBarInput b = bar.input;
    String timeRange = fmtYear(b.start()) + " — " + fmtYear(b.end());
    return new UnitSwimMatrixDTO.Bar(
        b.title(),
        b.boxId(),
        b.boxId(),
        b.title(),
        fmtPct(unitLeftPct),
        fmtPct(unitWidthPct),
        fmtPct(unitLeftPct),
        fmtPct(unitWidthPct),
        fmtRpx(chipLeftRpx),
        fmtRpx(SHICHEN_CHIP_RPX),
        fmtRpx(lineLeftRpx),
        fmtRpx(lineRightLft),
        fmtRpx(lineRightRpx),
        b.priority(),
        "default",
        10,
        timeRange
    );
  }

  private static UnitSwimMatrixDTO.Bar toIsolatedBar(
      SwimBarInput b,
      double leftPct,
      double widthPct,
      int startYear,
      int span
  ) {
    String left = fmtPct(leftPct);
    String width = fmtPct(widthPct);
    String timeRange = fmtYear(b.start()) + " — " + fmtYear(b.end());
    return new UnitSwimMatrixDTO.Bar(
        b.title(),
        b.boxId(),
        b.boxId(),
        b.title(),
        left,
        width,
        left,
        width,
        left,
        width,
        "0%",
        left,
        width,
        b.priority(),
        "default",
        10,
        timeRange
    );
  }

  private static double calcContinuousChipWidth(String title) {
    int len = title == null ? 0 : title.length();
    return Math.max(CONTINUOUS_MIN_CHIP, len * CONTINUOUS_CHAR_W + CONTINUOUS_PAD_RPX);
  }

  private static double pctYear(double year, int startYear, int span) {
    return Math.max(0, Math.min(100, 100.0 * (year - startYear) / span));
  }

  private static double pctSpan(double start, double end, int startYear, int span) {
    return Math.max(0, Math.min(100, 100.0 * (end - start) / span));
  }

  private static String fmtPct(double v) {
    return String.format("%.2f%%", v);
  }

  private static String fmtRpx(double v) {
    return String.format("%.2f", v) + "rpx";
  }

  private static String fmtYear(int y) {
    if (y < 0) return "前" + Math.abs(y);
    return String.valueOf(y);
  }

  private static double parsePct(String pct) {
    if (pct == null || pct.isBlank()) return 0;
    return Double.parseDouble(pct.replace("%", "").trim());
  }

  private static UnitSwimMatrixDTO.Bar withZIndex(UnitSwimMatrixDTO.Bar bar, int zIndex) {
    return new UnitSwimMatrixDTO.Bar(
        bar.title(),
        bar.boxId(),
        bar.boxKey(),
        bar.boxTitle(),
        bar.left(),
        bar.width(),
        bar.unitLeft(),
        bar.unitWidth(),
        bar.chipLeft(),
        bar.chipWidth(),
        bar.lineLeftW(),
        bar.lineRightL(),
        bar.lineRightW(),
        bar.priority(),
        bar.type(),
        zIndex,
        bar.timeRange()
    );
  }

  private record PlacedContinuous(
      SwimBarInput bar,
      int row,
      double unitLeftPct,
      double unitWidthPct,
      double chipLeftRpx,
      double chipWRpx,
      double lineLeftW,
      double lineRightL,
      double lineRightW
  ) {}

  private record PlacedShichen(SwimBarInput input, UnitSwimMatrixDTO.Bar bar, int row) {}

  private record PlacedIsolated(SwimBarInput input, int row, double leftPct, double widthPct) {}

  private static final class ShichenNorm {
    final SwimBarInput input;
    final int birth;
    final int death;
    final int appearStart;
    final int appearEnd;

    private ShichenNorm(
        SwimBarInput input,
        int birth,
        int death,
        int appearStart,
        int appearEnd
    ) {
      this.input = input;
      this.birth = birth;
      this.death = death;
      this.appearStart = appearStart;
      this.appearEnd = appearEnd;
    }

    static ShichenNorm from(SwimBarInput bar) {
      int birth = bar.start();
      int death = bar.end();
      if (death <= birth) death = birth + 1;
      int life = Math.max(death - birth, 1);
      int span = Math.min(SHICHEN_APPEAR_MAX, Math.max(SHICHEN_APPEAR_MIN, (int) Math.round(life * 0.22)));
      int mid = birth + (int) Math.round(life * 0.48);
      int appearStart = Math.max(birth, mid - span / 2);
      int appearEnd = Math.min(death, appearStart + span);
      if (appearEnd - appearStart < SHICHEN_APPEAR_MIN) {
        appearEnd = Math.min(death, appearStart + SHICHEN_APPEAR_MIN);
      }
      appearStart = Math.max(birth, Math.min(appearStart, death - 1));
      appearEnd = Math.max(appearStart + 1, Math.min(appearEnd, death));
      return new ShichenNorm(bar, birth, death, appearStart, appearEnd);
    }
  }
}
