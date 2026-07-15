package com.pandahis.histomap.contentgraph.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class SwimTimeScaleTest {

  @Test
  void sparseDynastyStaysNearLinear() {
    SwimTimeScale.Plan plan = SwimTimeScale.plan(-2070, -1600, java.util.List.of(-2050, -1919, -1652), 3);

    assertEquals("linear", plan.timeScaleMode());
    assertEquals(1, plan.timeSegments().size());
    assertTrue(plan.sheetWidthRpx() >= SwimTimeScale.MIN_SHEET_RPX);
    assertTrue(plan.sheetWidthRpx() <= SwimTimeScale.MAX_SHEET_RPX);
  }

  @Test
  void denseClusterCreatesMultipleSegments() {
    java.util.List<Integer> anchors = new java.util.ArrayList<>();
    for (int y = -180; y <= 8; y += 2) {
      anchors.add(y);
    }
    SwimTimeScale.Plan plan = SwimTimeScale.plan(-202, 8, anchors, 8);

    assertEquals("segmented", plan.timeScaleMode());
    assertTrue(plan.timeSegments().size() >= 2);
    assertTrue(plan.sheetWidthRpx() > SwimTimeScale.MIN_SHEET_RPX);
  }

  @Test
  void denseSegmentGetsMoreWidthThanSparseSegment() {
    java.util.List<Integer> anchors = new java.util.ArrayList<>();
    anchors.add(-2000);
    anchors.add(-1990);
    for (int y = -150; y <= 0; y += 3) {
      anchors.add(y);
    }
    SwimTimeScale.Plan plan = SwimTimeScale.plan(-2100, 8, anchors, 6);

    double maxWidth = 0;
    double minWidth = 100;
    for (var seg : plan.timeSegments()) {
      double width = Double.parseDouble(seg.width().replace("%", ""));
      maxWidth = Math.max(maxWidth, width);
      if (seg.boxCount() > 0) {
        minWidth = Math.min(minWidth, width);
      }
    }
    assertTrue(maxWidth > minWidth * 1.5);
  }

  @Test
  void percentForYearIsMonotonicAcrossSegments() {
    java.util.List<Integer> anchors = java.util.List.of(-190, -120, -80, -40, -10, 0);
    SwimTimeScale.Plan plan = SwimTimeScale.plan(-202, 8, anchors, 4);
    SwimTimeScale scale = plan.scale();

    double prev = -1;
    for (int y = -202; y <= 8; y += 7) {
      double pct = scale.percentForYear(y);
      assertTrue(pct >= prev);
      prev = pct;
    }
    assertEquals(0.0, scale.percentForYear(-202), 0.01);
    assertEquals(100.0, scale.percentForYear(8), 0.01);
  }

  @Test
  void ancientLongSpanKeepsTickLabelsSpaced() {
    SwimTimeScale.Plan plan = SwimTimeScale.plan(-2698, -2070, java.util.List.of(), 0);
    int sheet = plan.sheetWidthRpx();
    int span = -2070 - (-2698);

    long visibleLabels = plan.ticks().stream().filter(t -> !t.hideLabel()).count();
    assertTrue(visibleLabels <= 30, "远古长跨度不应生成过密标签，实际=" + visibleLabels);

    double prevPx = -1;
    for (var tick : plan.ticks()) {
      if (tick.hideLabel()) {
        continue;
      }
      double pct = Double.parseDouble(tick.left().replace("%", ""));
      double px = sheet * pct / 100.0;
      if (prevPx >= 0) {
        assertTrue(
            px - prevPx >= SwimTimeScale.MIN_LABEL_SPACING_RPX * 0.92,
            "相邻标签间距过近: " + (px - prevPx) + "rpx"
        );
      }
      prevPx = px;
    }

    int step = (int) Math.round((double) span / Math.max(1, visibleLabels));
    assertTrue(step >= 20, "五帝跨度刻度步长应>=20年，实际约" + step);
  }

  @Test
  void sparseGapsAreCompactedEvenWhenThereAreFewerThanEightAnchors() {
    java.util.List<Integer> anchors = java.util.List.of(-2698, -2540, -2360, -2200, -2070);
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-2698, -2070, anchors, 5);
    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        anchors,
        4200,
        initial.timeScaleMode()
    );

    assertEquals("segmented", fitted.timeScaleMode());
    assertGapsAtMost(fitted, anchors, SwimTimeScale.MAX_EMPTY_GAP_RPX);
    assertTrue(fitted.sheetWidthRpx() < 4200);
  }

  @Test
  void prefixAndSuffixUseStricterCapThanTheMiddleDesert() {
    java.util.List<Integer> anchors = java.util.List.of(-900, -890, -500, -490);
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-1200, -200, anchors, 4);
    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        anchors,
        5000,
        initial.timeScaleMode()
    );

    java.util.List<Integer> boundaries = new java.util.ArrayList<>();
    boundaries.add(-1200);
    boundaries.addAll(anchors);
    boundaries.add(-200);
    assertGapsAtMost(fitted, boundaries, SwimTimeScale.MAX_EMPTY_GAP_RPX);
    assertTrue(
        pixelGap(fitted.scale(), -1200, anchors.get(0), fitted.sheetWidthRpx())
            <= SwimTimeScale.MAX_EDGE_EMPTY_GAP_RPX + 1.0
    );
    assertTrue(
        pixelGap(fitted.scale(), anchors.get(anchors.size() - 1), -200, fitted.sheetWidthRpx())
            <= SwimTimeScale.MAX_EDGE_EMPTY_GAP_RPX + 1.0
    );
  }

  @Test
  void fittingSparseEdgesDoesNotCompressAlreadyComfortableDenseIntervals() {
    java.util.List<Integer> anchors = new java.util.ArrayList<>();
    for (int year = -200; year <= 0; year += 5) {
      anchors.add(year);
    }
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-220, 20, anchors, 8);
    int requestedWidth = 3600;
    double before = pixelGap(initial.scale(), -100, -95, requestedWidth);

    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        anchors,
        requestedWidth,
        initial.timeScaleMode()
    );
    double after = pixelGap(fitted.scale(), -100, -95, fitted.sheetWidthRpx());

    assertTrue(fitted.sheetWidthRpx() < requestedWidth);
    assertEquals(before, after, 0.1);
  }

  @Test
  void compactingDesertsPreservesDenseClusterSpacingInTheSameTimeline() {
    java.util.List<Integer> anchors = new java.util.ArrayList<>(
        java.util.List.of(-1100, -1095, -500)
    );
    for (int year = -495; year <= -450; year += 5) {
      anchors.add(year);
    }
    anchors.add(-100);
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-1200, 0, anchors, 8);
    int requestedWidth = 5000;
    double denseGapBefore = pixelGap(initial.scale(), -490, -485, requestedWidth);

    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        anchors,
        requestedWidth,
        initial.timeScaleMode()
    );
    double denseGapAfter = pixelGap(fitted.scale(), -490, -485, fitted.sheetWidthRpx());

    assertTrue(fitted.sheetWidthRpx() < requestedWidth);
    assertEquals(denseGapBefore, denseGapAfter, 0.05);
    java.util.List<Integer> boundaries = new java.util.ArrayList<>();
    boundaries.add(-1200);
    boundaries.addAll(anchors);
    boundaries.add(0);
    assertGapsAtMost(fitted, boundaries, SwimTimeScale.MAX_EMPTY_GAP_RPX);
  }

  @Test
  void emptyTimelineDoesNotCreateAHorizontallyScrollableBlankCanvas() {
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-1000, -500, java.util.List.of(), 0);
    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        java.util.List.of(),
        4200,
        initial.timeScaleMode()
    );

    assertEquals(SwimTimeScale.VIEWPORT_RPX, fitted.sheetWidthRpx());
    assertEquals("linear", fitted.timeScaleMode());
  }

  @Test
  void singleEdgeAnchorUsesOneViewportInsteadOfScalingItsOnlyDesert() {
    java.util.List<Integer> anchors = java.util.List.of(-1000);
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-1000, -500, anchors, 1);
    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        anchors,
        900,
        initial.timeScaleMode()
    );

    assertEquals(SwimTimeScale.VIEWPORT_RPX, fitted.sheetWidthRpx());
    assertEquals(0.0, fitted.scale().percentForYear(-1000), 0.01);
  }

  @Test
  void singleEndAnchorAlsoUsesOneViewport() {
    java.util.List<Integer> anchors = java.util.List.of(-500);
    SwimTimeScale.Plan initial = SwimTimeScale.plan(-1000, -500, anchors, 1);
    SwimTimeScale.Plan fitted = initial.scale().fitToViewport(
        anchors,
        900,
        initial.timeScaleMode()
    );

    assertEquals(SwimTimeScale.VIEWPORT_RPX, fitted.sheetWidthRpx());
    assertEquals(100.0, fitted.scale().percentForYear(-500), 0.01);
  }

  private static void assertGapsAtMost(
      SwimTimeScale.Plan plan,
      java.util.List<Integer> years,
      int maximumRpx
  ) {
    for (int i = 0; i < years.size() - 1; i++) {
      double gap = pixelGap(plan.scale(), years.get(i), years.get(i + 1), plan.sheetWidthRpx());
      assertTrue(
          gap <= maximumRpx + 1.0,
          years.get(i) + " 到 " + years.get(i + 1) + " 的空档过宽: " + gap + "rpx"
      );
    }
  }

  private static double pixelGap(SwimTimeScale scale, int fromYear, int toYear, int sheetWidthRpx) {
    return (scale.percentForYear(toYear) - scale.percentForYear(fromYear)) * sheetWidthRpx / 100.0;
  }
}
