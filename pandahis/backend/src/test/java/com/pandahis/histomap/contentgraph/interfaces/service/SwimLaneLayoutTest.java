package com.pandahis.histomap.contentgraph.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class SwimLaneLayoutTest {

  @Test
  void priorityViewsFoldBarsAboveSelectedThresholdIntoExtra() {
    List<SwimLaneLayout.SwimBarInput> bars = List.of(
        bar("GLBL_00001", "元祐更化", 1086, 1094, "p0"),
        bar("GLBL_00002", "熙宁变法", 1069, 1076, "p1"),
        bar("GLBL_00003", "崇宁党禁", 1102, 1106, "p2")
    );

    Map<String, UnitSwimMatrixDTO.LaneView> views =
        SwimLaneLayout.buildPriorityViews(bars, 1067, 40, 1440);

    UnitSwimMatrixDTO.LaneView p0 = views.get("p0");
    UnitSwimMatrixDTO.LaneView p1 = views.get("p1");

    assertEquals(1, p0.visibleCount());
    assertEquals(2, p0.moreCount());
    assertTrue(p0.extraBars().stream().anyMatch(b -> "GLBL_00002".equals(b.boxId())));
    assertEquals(2, p1.visibleCount());
    assertEquals(1, p1.moreCount());
  }

  @Test
  void priorityViewsCapVisibleRowsAtTen() {
    List<SwimLaneLayout.SwimBarInput> bars = java.util.stream.IntStream.rangeClosed(1, 12)
        .mapToObj(i -> bar(String.format("GLBL_%05d", i), "同年史略" + i, 1000, 1001, "p0"))
        .toList();

    UnitSwimMatrixDTO.LaneView view =
        SwimLaneLayout.buildPriorityViews(bars, 990, 40, 1440).get("p0");

    assertEquals(10, view.rowCount());
    assertEquals(10, view.visibleCount());
    assertEquals(2, view.moreCount());
    assertEquals(2, view.extraBars().size());
  }

  @Test
  void priorityViewsSortByPriorityPeakYearThenGlobalId() {
    List<SwimLaneLayout.SwimBarInput> bars = List.of(
        bar("GLBL_00010", "较早低优先级", 1001, 1002, "p2"),
        bar("GLBL_00004", "同峰值小ID", 1001, 1006, "p0", 1005),
        bar("GLBL_00005", "同峰值大ID", 1002, 1006, "p0", 1005),
        bar("GLBL_00003", "更晚高优先级", 1003, 1011, "p0", 1010)
    );

    UnitSwimMatrixDTO.LaneView view =
        SwimLaneLayout.buildPriorityViews(bars, 990, 40, 1440).get("p3");

    assertTrue(rowOf(view, "GLBL_00004") < rowOf(view, "GLBL_00005"));
    assertTrue(rowOf(view, "GLBL_00003") < rowOf(view, "GLBL_00010"));
  }

  @Test
  void peakYearAnchorsChipLeftWhenPresent() {
    UnitSwimMatrixDTO.LaneView view = SwimLaneLayout.buildPriorityViews(
        List.of(bar("GLBL_00020", "峰值定位", 1000, 1010, "p0", 1020)),
        1000,
        100,
        1440
    ).get("p0");

    UnitSwimMatrixDTO.Bar chip = view.collapsedRows().get(0).get(0);

    assertEquals("20.00%", chip.left());
    assertEquals(1020, chip.peakYear());
  }

  @Test
  void startYearAnchorsChipLeftWhenPeakYearMissing() {
    UnitSwimMatrixDTO.LaneView view = SwimLaneLayout.buildPriorityViews(
        List.of(bar("GLBL_00021", "君王定位", 1000, 1010, "p0")),
        1000,
        100,
        1440
    ).get("p0");

    UnitSwimMatrixDTO.Bar chip = view.collapsedRows().get(0).get(0);

    assertEquals("1.39%", chip.left());
    assertNull(chip.peakYear());
  }

  @Test
  void anchorAtStartKeepsPeakYearForDisplay() {
    UnitSwimMatrixDTO.LaneView view = SwimLaneLayout.buildPriorityViews(
        List.of(new SwimLaneLayout.SwimBarInput(
            "GLBL_00022",
            "君王展示",
            1000,
            1010,
            "p0",
            1005,
            "即位为君",
            true
        )),
        1000,
        100,
        1440
    ).get("p0");

    UnitSwimMatrixDTO.Bar chip = view.collapsedRows().get(0).get(0);

    assertEquals("1.39%", chip.left());
    assertEquals(1005, chip.peakYear());
    assertEquals("即位为君", chip.peakReason());
  }

  @Test
  void invalidGlobalIdFailsFast() {
    List<SwimLaneLayout.SwimBarInput> bars = List.of(
        bar("BOX_1", "非法编号", 1000, 1001, "p0")
    );

    assertThrows(
        IllegalArgumentException.class,
        () -> SwimLaneLayout.buildPriorityViews(bars, 990, 40, 1440)
    );
  }

  private static SwimLaneLayout.SwimBarInput bar(
      String boxId,
      String title,
      int start,
      int end,
      String priority
  ) {
    return new SwimLaneLayout.SwimBarInput(boxId, title, start, end, priority, null, null, false);
  }

  private static SwimLaneLayout.SwimBarInput bar(
      String boxId,
      String title,
      int start,
      int end,
      String priority,
      Integer peakYear
  ) {
    return new SwimLaneLayout.SwimBarInput(boxId, title, start, end, priority, peakYear, null, false);
  }

  private static int rowOf(UnitSwimMatrixDTO.LaneView view, String boxId) {
    for (int row = 0; row < view.collapsedRows().size(); row++) {
      for (UnitSwimMatrixDTO.Bar bar : view.collapsedRows().get(row)) {
        if (boxId.equals(bar.boxId())) {
          return row;
        }
      }
    }
    return Integer.MAX_VALUE;
  }
}
