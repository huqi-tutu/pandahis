package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.List;

/** 将泳道布局铺平为画布坐标（8rpx 网格吸附）。 */
final class SwimCanvasLayout {
  static final int GRID_RPX = 8;
  static final int CANVAS_PAD_LEFT_RPX = 40;
  static final int CATEGORY_PILL_W_RPX = 40;
  static final int BAND_GAP_RPX = 24;
  static final int BAND_PAD_RPX = 16;
  static final int MIN_BAND_HEIGHT_RPX = 56;

  private SwimCanvasLayout() {}

  record CanvasPlan(
      int canvasHeightRpx,
      int canvasPadLeftRpx,
      List<UnitSwimMatrixDTO.CategoryBand> categoryBands,
      List<UnitSwimMatrixDTO.Lane> lanes
  ) {}

  static CanvasPlan build(List<UnitSwimMatrixDTO.Lane> lanes) {
    List<UnitSwimMatrixDTO.CategoryBand> bands = new ArrayList<>();
    List<UnitSwimMatrixDTO.Lane> canvasLanes = new ArrayList<>();
    int cursor = BAND_PAD_RPX;

    for (UnitSwimMatrixDTO.Lane lane : lanes) {
      int trackHeight = snap(SwimLaneLayout.trackHeight(Math.max(1, lane.rowCount())));
      int bandHeight = Math.max(MIN_BAND_HEIGHT_RPX, trackHeight);
      bandHeight = snap(bandHeight);

      List<List<UnitSwimMatrixDTO.Bar>> canvasRows = new ArrayList<>();
      int rowIndex = 0;
      for (List<UnitSwimMatrixDTO.Bar> row : lane.collapsedRows()) {
        List<UnitSwimMatrixDTO.Bar> canvasRow = new ArrayList<>();
        int topRpx = snap(cursor + BAND_PAD_RPX + rowIndex * (SwimLaneLayout.CHIP_HEIGHT_RPX + SwimLaneLayout.ROW_GAP_RPX));
        for (UnitSwimMatrixDTO.Bar bar : row) {
          canvasRow.add(withCanvasPosition(bar, topRpx));
        }
        canvasRows.add(canvasRow);
        rowIndex++;
      }

      bands.add(new UnitSwimMatrixDTO.CategoryBand(
          lane.key(),
          lane.label(),
          lane.borderColor(),
          cursor,
          bandHeight,
          lane.readProgressText(),
          lane.totalCount()
      ));

      canvasLanes.add(new UnitSwimMatrixDTO.Lane(
          lane.key(),
          lane.label(),
          lane.icon(),
          lane.borderColor(),
          lane.layout(),
          lane.totalCount(),
          lane.readCount(),
          lane.readProgressText(),
          canvasRows,
          lane.hasMore(),
          lane.moreCount(),
          lane.moreBarLeft(),
          lane.moreBarWidth(),
          lane.extraBars(),
          lane.priorityViews(),
          lane.rowCount(),
          bandHeight,
          lane.visibleCount()
      ));

      cursor += bandHeight + BAND_GAP_RPX;
    }

    int canvasHeight = snap(Math.max(MIN_BAND_HEIGHT_RPX + BAND_PAD_RPX * 2, cursor + BAND_PAD_RPX));
    return new CanvasPlan(canvasHeight, CANVAS_PAD_LEFT_RPX, bands, canvasLanes);
  }

  private static UnitSwimMatrixDTO.Bar withCanvasPosition(UnitSwimMatrixDTO.Bar bar, int topRpx) {
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
        bar.zIndex(),
        bar.timeRange(),
        bar.startYear(),
        bar.endYear(),
        bar.peakYear(),
        bar.peakReason(),
        bar.globalIdNumber(),
        topRpx,
        SwimLaneLayout.CHIP_HEIGHT_RPX,
        bar.chipTag(),
        bar.priorityReason(),
        bar.entrySource()
    );
  }

  static int snap(int value) {
    if (value <= 0) {
      return 0;
    }
    return Math.max(GRID_RPX, Math.round(value / (float) GRID_RPX) * GRID_RPX);
  }

  static int snapRpx(double value) {
    return snap((int) Math.round(value));
  }
}
