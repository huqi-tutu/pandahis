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
}
