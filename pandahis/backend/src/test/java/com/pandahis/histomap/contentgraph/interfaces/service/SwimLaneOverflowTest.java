package com.pandahis.histomap.contentgraph.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class SwimLaneOverflowTest {

  @Test
  void sequentialJunwang_showsAllWithoutCollapse() {
    List<SwimLaneOverflow.BarSlice> shangJun = List.of(
        slice("GLBL_00046", "契", -1600, -1600),
        slice("GLBL_00060", "成汤", -1600, -1587),
        slice("GLBL_00045", "太甲", -1582, -1559),
        slice("GLBL_00086", "沃丁", -1559, -1541),
        slice("GLBL_00044", "太戊", -1487, -1412),
        slice("GLBL_00093", "祖乙", -1377, -1358),
        slice("GLBL_00138", "阳甲", -1321, -1317),
        slice("GLBL_00092", "盘庚", -1300, -1272),
        slice("GLBL_00055", "小辛", -1272, -1269),
        slice("GLBL_00054", "小乙", -1269, -1250),
        slice("GLBL_00073", "武丁", -1250, -1192),
        slice("GLBL_00094", "祖庚", -1192, -1185),
        slice("GLBL_00095", "祖甲", -1185, -1152),
        slice("GLBL_00059", "廪辛", -1152, -1146),
        slice("GLBL_00074", "武乙", -1138, -1103),
        slice("GLBL_00058", "帝辛（纣）", -1076, -1046)
    );

    assertTrue(SwimLaneOverflow.maxConcurrent(shangJun) <= SwimLaneOverflow.MAX_CONCURRENT);

    SwimLaneOverflow.Split split = SwimLaneOverflow.split(shangJun);
    assertEquals(16, split.visible().size());
    assertTrue(split.extra().isEmpty());
    assertTrue(split.visible().stream().anyMatch(b -> "GLBL_00058".equals(b.boxId())));
  }

  @Test
  void samePeriodOverflow_hidesLowestPriority() {
    List<SwimLaneOverflow.BarSlice> bars = new java.util.ArrayList<>();
    for (int i = 0; i < 12; i++) {
      bars.add(slice("B" + i, "人物" + i, 1000, 1100, i < 2 ? "p0" : "p3"));
    }

    assertTrue(SwimLaneOverflow.maxConcurrent(bars) > SwimLaneOverflow.MAX_CONCURRENT);

    SwimLaneOverflow.Split split = SwimLaneOverflow.split(bars);
    assertEquals(10, split.visible().size());
    assertEquals(2, split.extra().size());
    assertFalse(split.visible().stream().anyMatch(b -> b.boxId().equals("B11")));
    assertTrue(split.extra().stream().anyMatch(b -> b.boxId().equals("B11")));
  }

  private static SwimLaneOverflow.BarSlice slice(String id, String title, int start, int end) {
    return slice(id, title, start, end, "p2");
  }

  private static SwimLaneOverflow.BarSlice slice(
      String id,
      String title,
      int start,
      int end,
      String priority
  ) {
    return new SwimLaneOverflow.BarSlice(id, title, start, end, priority);
  }
}
