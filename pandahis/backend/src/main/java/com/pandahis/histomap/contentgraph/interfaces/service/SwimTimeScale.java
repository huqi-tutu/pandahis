package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.util.HistoryYearFormat;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

/** 朝代详情时间轴：按史略密度分段，段内线性、段间非等比拉伸。 */
final class SwimTimeScale {
  static final int MIN_SHEET_RPX = 1440;
  static final int MAX_SHEET_RPX = 5760;
  static final int TARGET_TICK_SPACING_RPX = 96;
  static final int VIEWPORT_RPX = 750;
  /** 内部相邻史略锚点最多间隔约半屏，避免一屏只露出边缘卡片。 */
  static final int MAX_EMPTY_GAP_RPX = 360;
  /** 首尾没有后续内容提示，留白应比内部间隔更紧。 */
  static final int MAX_EDGE_EMPTY_GAP_RPX = 240;
  /** 远古大年份标签（如「-2698」）比刻度线更宽，标签间距单独保底。 */
  static final int MIN_LABEL_SPACING_RPX = 104;
  /**
   * 网格线/刻度线的最小像素间距。分段步长各自独立计算，相邻两段交界处可能各出
   * 一根紧贴的候选线；即便文字标签会被碰撞检测隐藏，竖线本身仍会重复出现。
   * 生成候选后做一次全局去重，保证任意两根竖线都不会近到看起来像"重复线"。
   */
  static final int MIN_GRID_SPACING_RPX = 56;

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

  /**
   * 在保留密集区绝对像素间距的前提下压缩稀疏区。
   *
   * <p>映射以相邻史略锚点（含画布首尾）为边界：不超过上限的区间保持原宽，
   * 超出上限的区间压缩到固定宽度。这样高密时期不会因压缩空白而再次拥挤，
   * 稀疏时期也不会产生可横滑的一整屏空画布。完全没有锚点时，画布收敛为
   * 一个视口宽度，交由页面展示空状态，不保留无意义的横向滚动。</p>
   */
  Plan fitToViewport(List<Integer> anchorYears, int requestedSheetRpx, String currentMode) {
    int sourceSheetRpx = Math.max(VIEWPORT_RPX, requestedSheetRpx);
    List<Integer> anchors = normalizeAnchors(anchorYears, startYear, endYear);
    if (anchors.isEmpty()) {
      return linear(startYear, endYear).toPlan(VIEWPORT_RPX, "linear");
    }

    TreeSet<Integer> anchorBoundaries = new TreeSet<>();
    anchorBoundaries.add(startYear);
    anchorBoundaries.addAll(anchors);
    anchorBoundaries.add(endYear);

    List<RemapPoint> remapPoints = new ArrayList<>();
    double destinationRpx = 0.0;
    double previousSourceRpx = 0.0;
    boolean compacted = false;
    List<Integer> boundaryYears = new ArrayList<>(anchorBoundaries);
    for (int i = 0; i < boundaryYears.size(); i++) {
      int year = boundaryYears.get(i);
      double sourceRpx = percentForYear(year) * sourceSheetRpx / 100.0;
      if (remapPoints.isEmpty()) {
        remapPoints.add(new RemapPoint(sourceRpx, 0.0));
        previousSourceRpx = sourceRpx;
        continue;
      }
      double sourceGap = Math.max(0.0, sourceRpx - previousSourceRpx);
      int previousYear = boundaryYears.get(i - 1);
      boolean leadingEmptyEdge = previousYear == startYear && !anchors.contains(startYear);
      boolean trailingEmptyEdge = year == endYear && !anchors.contains(endYear);
      int gapLimit = leadingEmptyEdge || trailingEmptyEdge
          ? MAX_EDGE_EMPTY_GAP_RPX
          : MAX_EMPTY_GAP_RPX;
      double keptGap = Math.min(sourceGap, gapLimit);
      compacted = compacted || keptGap + 0.01 < sourceGap;
      destinationRpx += keptGap;
      remapPoints.add(new RemapPoint(sourceRpx, destinationRpx));
      previousSourceRpx = sourceRpx;
    }

    if (!compacted) {
      return toPlan(sourceSheetRpx, currentMode);
    }

    double destinationScale = destinationRpx < VIEWPORT_RPX
        ? VIEWPORT_RPX / Math.max(1.0, destinationRpx)
        : 1.0;
    if (destinationScale > 1.0) {
      remapPoints = remapPoints.stream()
          .map(point -> new RemapPoint(point.sourceRpx(), point.destinationRpx() * destinationScale))
          .toList();
      destinationRpx *= destinationScale;
    }

    TreeSet<Integer> controlYears = new TreeSet<>(anchorBoundaries);
    for (Segment segment : segments) {
      controlYears.add(segment.startYear());
      controlYears.add(segment.endYear());
    }

    List<Integer> years = new ArrayList<>(controlYears);
    List<MappedDraft> mappedDrafts = new ArrayList<>();
    for (int i = 0; i < years.size() - 1; i++) {
      int fromYear = years.get(i);
      int toYear = years.get(i + 1);
      if (toYear <= fromYear) {
        continue;
      }
      double fromSourceRpx = percentForYear(fromYear) * sourceSheetRpx / 100.0;
      double toSourceRpx = percentForYear(toYear) * sourceSheetRpx / 100.0;
      double fromDestinationRpx = mapRpx(remapPoints, fromSourceRpx);
      double toDestinationRpx = mapRpx(remapPoints, toSourceRpx);
      boolean firstInterval = i == 0;
      int boxCount = (int) anchors.stream()
          .filter(anchor -> (firstInterval ? anchor >= fromYear : anchor > fromYear) && anchor <= toYear)
          .count();
      appendOrMerge(
          mappedDrafts,
          new MappedDraft(fromYear, toYear, fromDestinationRpx, toDestinationRpx, boxCount)
      );
    }

    int fittedSheetRpx = Math.max(VIEWPORT_RPX, (int) Math.floor(destinationRpx));
    List<Segment> fittedSegments = new ArrayList<>();
    for (MappedDraft draft : mappedDrafts) {
      fittedSegments.add(new Segment(
          draft.startYear(),
          draft.endYear(),
          draft.leftRpx() / destinationRpx * 100.0,
          (draft.rightRpx() - draft.leftRpx()) / destinationRpx * 100.0,
          draft.boxCount()
      ));
    }
    String fittedMode = fittedSegments.size() > 1 ? "segmented" : "linear";
    SwimTimeScale fittedScale = new SwimTimeScale(startYear, endYear, fittedSegments);
    return fittedScale.toPlan(fittedSheetRpx, fittedMode, this.segments);
  }

  private Plan toPlan(int sheetWidthRpx, String mode) {
    return toPlan(sheetWidthRpx, mode, this.segments);
  }

  /**
   * 生成刻度 / 网格线 / 分段信息。
   *
   * <p>{@code tickSegments} 是刻度步长的参照分段（未压缩前的粗分段，代表真实的
   * 疏密节奏），与 {@code this.segments}（用于坐标映射、可能是压缩后的细分段）
   * 解耦：分段拉伸继续负责横向布局，刻度改为按规则步长在真实像素密度上生成，
   * 不再受任何分段边界强制打点，避免出现与拉伸细分段绑定的杂乱竖线。</p>
   */
  private Plan toPlan(int sheetWidthRpx, String mode, List<Segment> tickSegments) {
    List<UnitSwimMatrixDTO.TimeSegment> timeSegments = new ArrayList<>();
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
    }

    List<Candidate> candidates = new ArrayList<>();
    candidates.add(new Candidate(startYear, 0.0, true, false));

    for (Segment seg : tickSegments) {
      double leftPct = percentForYear(seg.startYear());
      double rightPct = percentForYear(seg.endYear());
      double effectiveWidthPct = Math.max(0.0, rightPct - leftPct);

      int segSpan = Math.max(1, seg.endYear() - seg.startYear());
      int step = tickStep(segSpan, effectiveWidthPct, sheetWidthRpx);
      int first = roundUpToStep(seg.startYear() + 1, step);
      for (int y = first; y < seg.endYear(); y += step) {
        double left = percentForYear(y);
        if (left <= 0.5 || left >= 99.5) {
          continue;
        }
        boolean hide = shouldHideTickLabel(y, seg.startYear(), seg.endYear(), step);
        candidates.add(new Candidate(y, left, false, hide));
      }
    }

    List<Candidate> deduped = dedupeCloseCandidates(candidates, sheetWidthRpx);

    List<UnitSwimMatrixDTO.AxisTick> ticks = new ArrayList<>(deduped.size());
    List<UnitSwimMatrixDTO.GridLine> gridLines = new ArrayList<>(deduped.size() + 1);
    for (Candidate c : deduped) {
      String left = fmtPct(c.leftPct());
      ticks.add(new UnitSwimMatrixDTO.AxisTick(HistoryYearFormat.label(c.year()), left, c.edgeStart(), c.hideLabel(), false));
      gridLines.add(new UnitSwimMatrixDTO.GridLine(left, false));
    }

    gridLines.add(new UnitSwimMatrixDTO.GridLine("100.00%", false));
    ticks = resolveTickLabelCollisions(ticks, sheetWidthRpx);
    return new Plan(this, sheetWidthRpx, ticks, gridLines, timeSegments, mode);
  }

  private record Candidate(int year, double leftPct, boolean edgeStart, boolean hideLabel) {}

  /**
   * 相邻分段各自计算步长，交界处可能各出一根紧贴的候选线；按像素排序后，
   * 与前一条保留线间距小于 {@link #MIN_GRID_SPACING_RPX} 的候选直接丢弃，
   * 保证任意两根竖线都有起码的呼吸间距，不会重复出现。
   */
  private static List<Candidate> dedupeCloseCandidates(List<Candidate> candidates, int sheetWidthRpx) {
    if (candidates.size() <= 1) {
      return candidates;
    }
    List<Candidate> sorted = new ArrayList<>(candidates);
    sorted.sort(java.util.Comparator.comparingDouble(Candidate::leftPct));

    double minGapPct = sheetWidthRpx <= 0 ? 0 : MIN_GRID_SPACING_RPX * 100.0 / sheetWidthRpx;
    List<Candidate> kept = new ArrayList<>(sorted.size());
    for (Candidate c : sorted) {
      if (!kept.isEmpty()) {
        Candidate last = kept.get(kept.size() - 1);
        if (c.leftPct() - last.leftPct() < minGapPct) {
          // 起点 / 有文字的刻度优先保留，避免被相邻段一个即将被隐藏文字的候选顶掉。
          if (!c.edgeStart() && (last.edgeStart() || !last.hideLabel() || c.hideLabel())) {
            continue;
          }
          kept.set(kept.size() - 1, c);
          continue;
        }
      }
      kept.add(c);
    }
    return kept;
  }

  /**
   * 标签像素间距不足时隐藏低优先级刻度，避免起点/终点/普通刻度叠字。
   *
   * <p>终点年份由前端单独渲染在 100% 处（{@code swim.endLabel}），并不在
   * {@code ticks} 列表中，因此这里额外注入一个虚拟占位参与碰撞判定 ——
   * 它能让邻近的普通刻度让位，但本身永远不会被写回 {@code ticks}。</p>
   */
  private static List<UnitSwimMatrixDTO.AxisTick> resolveTickLabelCollisions(
      List<UnitSwimMatrixDTO.AxisTick> ticks,
      int sheetWidthRpx
  ) {
    if (ticks.isEmpty()) {
      return ticks;
    }

    List<TickSlot> slots = new ArrayList<>();
    for (int i = 0; i < ticks.size(); i++) {
      UnitSwimMatrixDTO.AxisTick tick = ticks.get(i);
      slots.add(new TickSlot(
          i,
          tick,
          parsePct(tick.left()) * sheetWidthRpx / 100.0,
          tick.hideLabel()
      ));
    }

    slots.sort(java.util.Comparator.comparingDouble(slot -> slot.px));
    List<TickSlot> kept = new ArrayList<>();
    TickSlot endAnchor = new TickSlot(-1, null, sheetWidthRpx, false);
    kept.add(endAnchor);

    for (TickSlot slot : slots) {
      if (slot.hideLabel) {
        continue;
      }
      TickSlot conflict = null;
      for (TickSlot other : kept) {
        if (Math.abs(slot.px - other.px) < MIN_LABEL_SPACING_RPX) {
          conflict = other;
          break;
        }
      }
      if (conflict == null) {
        kept.add(slot);
        continue;
      }
      int conflictPriority = conflict.tick == null ? 3 : tickPriority(conflict.tick);
      if (tickPriority(slot.tick) > conflictPriority) {
        if (conflict.tick != null) {
          conflict.hideLabel = true;
          kept.remove(conflict);
        }
        kept.add(slot);
      } else {
        slot.hideLabel = true;
      }
    }

    boolean[] hide = new boolean[ticks.size()];
    for (TickSlot slot : slots) {
      hide[slot.index] = slot.hideLabel;
    }

    List<UnitSwimMatrixDTO.AxisTick> out = new ArrayList<>(ticks.size());
    for (int i = 0; i < ticks.size(); i++) {
      UnitSwimMatrixDTO.AxisTick tick = ticks.get(i);
      if (hide[i] == tick.hideLabel()) {
        out.add(tick);
        continue;
      }
      out.add(new UnitSwimMatrixDTO.AxisTick(
          tick.label(),
          tick.left(),
          tick.edgeStart(),
          hide[i],
          tick.segmentBoundary()
      ));
    }
    return out;
  }

  private static int tickPriority(UnitSwimMatrixDTO.AxisTick tick) {
    if (tick.edgeStart()) {
      return 3;
    }
    if (tick.segmentBoundary()) {
      return 2;
    }
    return 1;
  }

  private static double parsePct(String left) {
    return Double.parseDouble(left.replace("%", ""));
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
    Set<Integer> cuts = new TreeSet<>();
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
        boolean afterStart = i == 0 ? anchor >= segStart : anchor > segStart;
        if (afterStart && anchor <= segEnd) {
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

  private static double mapRpx(List<RemapPoint> points, double sourceRpx) {
    for (int i = 0; i < points.size() - 1; i++) {
      RemapPoint from = points.get(i);
      RemapPoint to = points.get(i + 1);
      if (sourceRpx > to.sourceRpx()) {
        continue;
      }
      double sourceSpan = Math.max(1.0, to.sourceRpx() - from.sourceRpx());
      double fraction = Math.max(0.0, Math.min(1.0, (sourceRpx - from.sourceRpx()) / sourceSpan));
      return from.destinationRpx() + fraction * (to.destinationRpx() - from.destinationRpx());
    }
    return points.get(points.size() - 1).destinationRpx();
  }

  private static void appendOrMerge(List<MappedDraft> drafts, MappedDraft next) {
    if (drafts.isEmpty()) {
      drafts.add(next);
      return;
    }
    MappedDraft previous = drafts.get(drafts.size() - 1);
    double previousSlope = previous.pixelSlope();
    double nextSlope = next.pixelSlope();
    double slopeTolerance = Math.max(0.0001, Math.max(Math.abs(previousSlope), Math.abs(nextSlope)) * 0.000001);
    if (Math.abs(previousSlope - nextSlope) <= slopeTolerance && previous.endYear() == next.startYear()) {
      drafts.set(
          drafts.size() - 1,
          new MappedDraft(
              previous.startYear(),
              next.endYear(),
              previous.leftRpx(),
              next.rightRpx(),
              previous.boxCount() + next.boxCount()
          )
      );
      return;
    }
    drafts.add(next);
  }

  private record RemapPoint(double sourceRpx, double destinationRpx) {}

  private record MappedDraft(
      int startYear,
      int endYear,
      double leftRpx,
      double rightRpx,
      int boxCount
  ) {
    double pixelSlope() {
      return (rightRpx - leftRpx) / Math.max(1, endYear - startYear);
    }
  }

  private static final class TickSlot {
    final int index;
    final UnitSwimMatrixDTO.AxisTick tick;
    final double px;
    boolean hideLabel;

    TickSlot(int index, UnitSwimMatrixDTO.AxisTick tick, double px, boolean hideLabel) {
      this.index = index;
      this.tick = tick;
      this.px = px;
      this.hideLabel = hideLabel;
    }
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

