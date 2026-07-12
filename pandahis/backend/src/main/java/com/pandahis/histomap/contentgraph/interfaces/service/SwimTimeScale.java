package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.util.HistoryYearFormat;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

/** 朝代详情时间轴：按史略密度分段，段内线性、段间非等比拉伸。 */
final class SwimTimeScale {
  static final int MIN_SHEET_RPX = 1440;
  static final int MAX_SHEET_RPX = 5760;
  static final int TARGET_TICK_SPACING_RPX = 96;
  /** 远古大年份标签（如「-2698」）比刻度线更宽，标签间距单独保底。 */
  static final int MIN_LABEL_SPACING_RPX = 104;

  private final int startYear;
  private final int endYear;
  private final List<Segment> segments;

  record Segment(int startYear, int endYear, double leftPct, double widthPct, int boxCount) {
    boolean dense() {
      int years = Math.max(1, endYear - startYear);
      return boxCount > 0 && ((double) boxCount / years) >= 0.35;
    }
  }

  record Plan(
      SwimTimeScale scale,
      int sheetWidthRpx,
      List<UnitSwimMatrixDTO.AxisTick> ticks,
      List<UnitSwimMatrixDTO.GridLine> gridLines,
      List<UnitSwimMatrixDTO.TimeSegment> timeSegments,
      String timeScaleMode
  ) {}

  private SwimTimeScale(int startYear, int endYear, List<Segment> segments) {
    this.startYear = startYear;
    this.endYear = endYear;
    this.segments = List.copyOf(segments);
  }

  static Plan plan(int startYear, int endYear, List<Integer> anchorYears, int laneSeedCount) {
    int span = Math.max(1, endYear - startYear);
    List<Integer> anchors = normalizeAnchors(anchorYears, startYear, endYear);

    if (anchors.isEmpty() || span <= 12) {
      SwimTimeScale linear = linear(startYear, endYear);
      int sheet = MIN_SHEET_RPX;
      return linear.toPlan(sheet, "linear");
    }

    List<Integer> cuts = buildCutPoints(startYear, endYear, anchors, span);
    List<SegmentDraft> drafts = buildDrafts(startYear, endYear, cuts, anchors, span);
    assignWeights(drafts, span, anchors.size());
    List<Segment> segments = toSegments(drafts);
    String mode = resolveMode(segments);
    SwimTimeScale scale = "segmented".equals(mode)
        ? new SwimTimeScale(startYear, endYear, segments)
        : linear(startYear, endYear);
    int sheet = scale.recommendSheetWidth(anchors.size(), laneSeedCount);
    return scale.toPlan(sheet, mode);
  }

  private static String resolveMode(List<Segment> segments) {
    if (segments.size() <= 1) {
      return "linear";
    }
    int totalBoxes = segments.stream().mapToInt(Segment::boxCount).sum();
    if (totalBoxes < 8) {
      return "linear";
    }
    double maxWidth = 0;
    double minWidth = 100;
    boolean anyDense = false;
    for (Segment seg : segments) {
      maxWidth = Math.max(maxWidth, seg.widthPct());
      if (seg.widthPct() > 0) {
        minWidth = Math.min(minWidth, seg.widthPct());
      }
      anyDense = anyDense || seg.dense();
    }
    if (anyDense || maxWidth >= minWidth * 1.8) {
      return "segmented";
    }
    return "linear";
  }

  static SwimTimeScale linear(int startYear, int endYear) {
    int span = Math.max(1, endYear - startYear);
    return new SwimTimeScale(
        startYear,
        endYear,
        List.of(new Segment(startYear, endYear, 0.0, 100.0, 0))
    );
  }

  double percentForYear(int year) {
    int y = Math.max(startYear, Math.min(endYear, year));
    for (Segment seg : segments) {
      if (y < seg.startYear() || y > seg.endYear()) {
        continue;
      }
      int segSpan = Math.max(1, seg.endYear() - seg.startYear());
      double frac = (double) (y - seg.startYear()) / segSpan;
      return seg.leftPct() + frac * seg.widthPct();
    }
    return 100.0;
  }

  List<Segment> segments() {
    return segments;
  }

  int startYear() {
    return startYear;
  }

  int endYear() {
    return endYear;
  }

  Plan replan(int sheetWidthRpx, String mode) {
    return toPlan(sheetWidthRpx, mode);
  }

  private Plan toPlan(int sheetWidthRpx, String mode) {
    List<UnitSwimMatrixDTO.AxisTick> ticks = new ArrayList<>();
    List<UnitSwimMatrixDTO.GridLine> gridLines = new ArrayList<>();
    List<UnitSwimMatrixDTO.TimeSegment> timeSegments = new ArrayList<>();

    ticks.add(new UnitSwimMatrixDTO.AxisTick(HistoryYearFormat.label(startYear), "0.00%", true, false, false));

    for (Segment seg : segments) {
      timeSegments.add(new UnitSwimMatrixDTO.TimeSegment(
          seg.startYear(),
          seg.endYear(),
          HistoryYearFormat.label(seg.startYear()),
          HistoryYearFormat.label(seg.endYear()),
          fmtPct(seg.leftPct()),
          fmtPct(seg.widthPct()),
          seg.boxCount(),
          seg.dense()
      ));

      if (seg.startYear() > startYear) {
        String left = fmtPct(seg.leftPct());
        ticks.add(new UnitSwimMatrixDTO.AxisTick(HistoryYearFormat.label(seg.startYear()), left, false, false, true));
        gridLines.add(new UnitSwimMatrixDTO.GridLine(left, true));
      }

      int segSpan = Math.max(1, seg.endYear() - seg.startYear());
      int step = tickStep(segSpan, seg.widthPct(), sheetWidthRpx);
      int first = roundUpToStep(seg.startYear() + 1, step);
      for (int y = first; y < seg.endYear(); y += step) {
        double left = percentForYear(y);
        if (left <= 0.5 || left >= 99.5) {
          continue;
        }
        boolean hide = shouldHideTickLabel(y, seg.startYear(), seg.endYear(), step);
        ticks.add(new UnitSwimMatrixDTO.AxisTick(HistoryYearFormat.label(y), fmtPct(left), false, hide, false));
        gridLines.add(new UnitSwimMatrixDTO.GridLine(fmtPct(left), false));
      }
    }

    return new Plan(this, sheetWidthRpx, ticks, gridLines, timeSegments, mode);
  }

  private int recommendSheetWidth(int anchorCount, int laneSeedCount) {
    int sheet = MIN_SHEET_RPX;
    for (Segment seg : segments) {
      if (seg.boxCount() <= 0) {
        continue;
      }
      double segPx = sheet * seg.widthPct() / 100.0;
      double neededPx = seg.boxCount() * (SwimLaneLayout.CHIP_MAX_RPX + SwimLaneLayout.CHIP_GAP_RPX) + 80;
      if (neededPx > segPx) {
        sheet = (int) Math.ceil(sheet * neededPx / Math.max(1.0, segPx) * 1.08);
      }
    }

    double spanFactor = Math.max(1.0, (double) (endYear - startYear) / 220.0);
    double densityFactor = Math.max(1.0, anchorCount / 80.0);
    sheet = (int) Math.round(sheet * Math.min(2.2, Math.max(1.0, Math.sqrt(spanFactor * densityFactor))));

    if (laneSeedCount > 0 && anchorCount > 120) {
      sheet = (int) Math.round(sheet * 1.15);
    }

    return Math.max(MIN_SHEET_RPX, Math.min(MAX_SHEET_RPX, sheet));
  }

  private static List<Integer> normalizeAnchors(List<Integer> anchorYears, int startYear, int endYear) {
    Set<Integer> out = new TreeSet<>();
    for (Integer year : anchorYears) {
      if (year == null) {
        continue;
      }
      int y = Math.max(startYear, Math.min(endYear, year));
      out.add(y);
    }
    return new ArrayList<>(out);
  }

  private static List<Integer> buildCutPoints(int startYear, int endYear, List<Integer> anchors, int span) {
    LinkedHashSet<Integer> cuts = new LinkedHashSet<>();
    cuts.add(startYear);

    int gapThreshold = Math.max(18, span / 7);
    int minSegmentYears = Math.max(8, span / 36);

    for (int i = 0; i < anchors.size() - 1; i++) {
      int gap = anchors.get(i + 1) - anchors.get(i);
      if (gap >= gapThreshold) {
        int cut = roundToNiceYear((anchors.get(i) + anchors.get(i + 1)) / 2);
        if (cut - startYear >= minSegmentYears && endYear - cut >= minSegmentYears) {
          cuts.add(cut);
        }
      }
    }

    if (!anchors.isEmpty()) {
      int prefix = anchors.get(0) - startYear;
      int suffix = endYear - anchors.get(anchors.size() - 1);
      int desertThreshold = Math.max(30, span / 5);
      if (prefix >= desertThreshold && prefix >= minSegmentYears * 2) {
        int cut = roundToNiceYear(startYear + prefix / 2);
        if (cut - startYear >= minSegmentYears && anchors.get(0) - cut >= minSegmentYears) {
          cuts.add(cut);
        }
      }
      if (suffix >= desertThreshold && suffix >= minSegmentYears * 2) {
        int cut = roundToNiceYear(anchors.get(anchors.size() - 1) + suffix / 2);
        if (cut - anchors.get(anchors.size() - 1) >= minSegmentYears && endYear - cut >= minSegmentYears) {
          cuts.add(cut);
        }
      }
    }

    double avgDensity = anchors.isEmpty() ? 0 : (double) anchors.size() / span;
    int maxGap = 0;
    for (int i = 0; i < anchors.size() - 1; i++) {
      maxGap = Math.max(maxGap, anchors.get(i + 1) - anchors.get(i));
    }
    if (avgDensity >= 0.22 && maxGap < gapThreshold / 2) {
      int parts = Math.min(6, Math.max(3, (int) Math.ceil(Math.sqrt(anchors.size()))));
      for (int i = 1; i < parts; i++) {
        int cut = startYear + (int) Math.round((double) span * i / parts);
        if (cut - startYear >= minSegmentYears && endYear - cut >= minSegmentYears) {
          cuts.add(cut);
        }
      }
    }

    cuts.add(endYear);
    return new ArrayList<>(cuts);
  }

  private static List<SegmentDraft> buildDrafts(
      int startYear,
      int endYear,
      List<Integer> cuts,
      List<Integer> anchors,
      int span
  ) {
    List<SegmentDraft> drafts = new ArrayList<>();
    for (int i = 0; i < cuts.size() - 1; i++) {
      int segStart = cuts.get(i);
      int segEnd = cuts.get(i + 1);
      if (segEnd <= segStart) {
        continue;
      }
      int count = 0;
      for (int anchor : anchors) {
        if (anchor >= segStart && anchor <= segEnd) {
          count++;
        }
      }
      drafts.add(new SegmentDraft(segStart, segEnd, count));
    }

    if (drafts.isEmpty()) {
      drafts.add(new SegmentDraft(startYear, endYear, anchors.size()));
    }
    return drafts;
  }

  private static void assignWeights(List<SegmentDraft> drafts, int span, int totalAnchors) {
    double chipYears = Math.max(2.0, Math.min(10.0, span / Math.max(18.0, totalAnchors * 1.4)));
    double totalWeight = 0;
    for (SegmentDraft draft : drafts) {
      int years = Math.max(1, draft.endYear - draft.startYear);
      double calendar = years * 0.30;
      double density = draft.boxCount * 5.5 * chipYears;
      double localBoost = 1.0;
      if (draft.boxCount > 0) {
        double ratio = (double) draft.boxCount / years;
        if (ratio >= 0.45) {
          localBoost = 1.0 + Math.min(1.2, ratio);
        }
      }
      draft.weight = Math.max(years * 0.10, (calendar + density) * localBoost);
      totalWeight += draft.weight;
    }

    double cursor = 0;
    for (SegmentDraft draft : drafts) {
      draft.leftPct = cursor;
      draft.widthPct = draft.weight / Math.max(1.0, totalWeight) * 100.0;
      cursor += draft.widthPct;
    }

    if (!drafts.isEmpty()) {
      SegmentDraft last = drafts.get(drafts.size() - 1);
      double drift = 100.0 - (last.leftPct + last.widthPct);
      last.widthPct += drift;
    }
  }

  private static List<Segment> toSegments(List<SegmentDraft> drafts) {
    List<Segment> segments = new ArrayList<>();
    for (SegmentDraft draft : drafts) {
      segments.add(new Segment(
          draft.startYear,
          draft.endYear,
          draft.leftPct,
          draft.widthPct,
          draft.boxCount
      ));
    }
    return segments;
  }

  private static int tickStep(int segSpanYears, double segWidthPct, int sheetWidthRpx) {
    double segPx = sheetWidthRpx * segWidthPct / 100.0;
    double yearsPerTickGrid = (TARGET_TICK_SPACING_RPX / Math.max(1.0, segPx)) * segSpanYears;
    double yearsPerTickLabel = (MIN_LABEL_SPACING_RPX / Math.max(1.0, segPx)) * segSpanYears;
    return niceStep(Math.max(yearsPerTickGrid, yearsPerTickLabel));
  }

  /** 取不小于 raw 的最近「整」步长，保证刻度间距不低于目标像素。 */
  private static int niceStep(double raw) {
    if (raw <= 1) return 1;
    if (raw <= 2) return 2;
    if (raw <= 5) return 5;
    if (raw <= 10) return 10;
    if (raw <= 20) return 20;
    if (raw <= 25) return 25;
    if (raw <= 50) return 50;
    if (raw <= 100) return 100;
    if (raw <= 200) return 200;
    if (raw <= 500) return 500;
    return 1000;
  }

  private static int roundUpToStep(int year, int step) {
    if (step <= 1) {
      return year;
    }
    int rem = Math.floorMod(year, step);
    if (rem == 0) {
      return year;
    }
    return year + (step - rem);
  }

  private static boolean shouldHideTickLabel(int year, int segStart, int segEnd, int step) {
    int distStart = year - segStart;
    int distEnd = segEnd - year;
    return distStart < step || distEnd < step;
  }

  private static int roundToNiceYear(int year) {
    int abs = Math.abs(year);
    int step = abs >= 1000 ? 50 : abs >= 200 ? 20 : abs >= 50 ? 10 : 5;
    if (year >= 0) {
      return Math.round(year / (float) step) * step;
    }
    return -Math.round(abs / (float) step) * step;
  }

  private static String fmtPct(double value) {
    return String.format("%.2f%%", value);
  }

  private static final class SegmentDraft {
    final int startYear;
    final int endYear;
    final int boxCount;
    double weight;
    double leftPct;
    double widthPct;

    SegmentDraft(int startYear, int endYear, int boxCount) {
      this.startYear = startYear;
      this.endYear = endYear;
      this.boxCount = boxCount;
    }
  }
}

