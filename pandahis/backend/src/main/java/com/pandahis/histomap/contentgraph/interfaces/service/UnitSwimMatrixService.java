package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.domain.BoxCategorySupport;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class UnitSwimMatrixService {
  private static final int SHEET_WIDTH_RPX = 1440;

  private final JdbcTemplate jdbcTemplate;
  private final UnitDynastyResolver dynastyResolver;

  public UnitSwimMatrixService(JdbcTemplate jdbcTemplate, UnitDynastyResolver dynastyResolver) {
    this.jdbcTemplate = jdbcTemplate;
    this.dynastyResolver = dynastyResolver;
  }

  public UnitSwimMatrixDTO load(String unitId) {
    String dynastyId = dynastyResolver.resolveDynastyId(unitId)
        .orElseThrow(() -> ApiException.notFound("unit not found"));
    Map<String, Object> dynasty = dynastyResolver.requireDynastyById(dynastyId);

    int startYear = dynastyResolver.dynastyStartYear(dynasty);
    int endYear = dynastyResolver.dynastyEndYear(dynasty);
    String dynastyName = Optional.ofNullable((String) dynasty.get("name")).orElse("").trim();
    String civName = dynastyResolver.civilizationName(dynasty);

    List<Map<String, Object>> boxes = jdbcTemplate.queryForList(
        "SELECT id, title, category_key, start_year, end_year, priority_code, importance_level, peak_year, blurb "
            + "FROM historical_box WHERE dynasty_id=? AND status=1 "
            + "ORDER BY start_year ASC, id ASC",
        dynastyId
    );

    List<UnitSwimMatrixDTO.AxisTick> ticks = buildTicks(startYear, endYear);
    String endLabel = fmtAxisYear(endYear);

    List<LaneSeed> laneSeeds = new ArrayList<>();
    for (BoxCategorySupport.CategoryDef def : BoxCategorySupport.swimLanes()) {
      List<SwimLaneLayout.SwimBarInput> bars = new ArrayList<>();
      for (Map<String, Object> b : boxes) {
        String cat = (String) b.get("category_key");
        Optional<String> laneKey = BoxCategorySupport.swimLaneKey(cat);
        if (laneKey.isEmpty() || !laneKey.get().equals(def.key())) continue;
        int bs = b.get("start_year") == null ? startYear : ((Number) b.get("start_year")).intValue();
        int be = b.get("end_year") == null ? bs : ((Number) b.get("end_year")).intValue();
        if (be <= bs) be = bs + 1;
        Integer peakYear = b.get("peak_year") == null ? null : ((Number) b.get("peak_year")).intValue();
        bars.add(new SwimLaneLayout.SwimBarInput(
            (String) b.get("id"),
            (String) b.get("title"),
            bs,
            be,
            priority(b.get("priority_code"), b.get("importance_level")),
            "junji".equals(def.key()) ? null : peakYear
        ));
      }
      laneSeeds.add(new LaneSeed(def, bars));
    }

    int sheetWidthRpx = computeSheetWidth(laneSeeds, startYear, endYear);
    List<UnitSwimMatrixDTO.Lane> lanes = laneSeeds.stream()
        .map(seed -> buildLane(seed.def(), seed.bars(), startYear, endYear, sheetWidthRpx))
        .toList();

    List<String> concurrent = loadConcurrentItems(civName, dynastyName, startYear, endYear);

    return new UnitSwimMatrixDTO(
        startYear,
        endYear,
        endLabel,
        ticks,
        lanes,
        concurrent,
        sheetWidthRpx
    );
  }

  private UnitSwimMatrixDTO.Lane buildLane(
      BoxCategorySupport.CategoryDef def,
      List<SwimLaneLayout.SwimBarInput> bars,
      int startYear,
      int endYear,
      int sheetWidthRpx
  ) {
    int span = Math.max(1, endYear - startYear);
    Map<String, UnitSwimMatrixDTO.LaneView> views =
        SwimLaneLayout.buildPriorityViews(bars, startYear, span, sheetWidthRpx);
    UnitSwimMatrixDTO.LaneView defaultView = views.get("p3");
    int totalCount = bars.size();
    // TODO: replace with real per-user read progress when the API exposes it.
    int readCount = 0;

    return new UnitSwimMatrixDTO.Lane(
        def.key(),
        def.label(),
        laneIcon(def.key()),
        BoxCategorySupport.laneBorderColor(def.key()),
        def.layout(),
        totalCount,
        readCount,
        readCount + "/" + totalCount,
        defaultView.collapsedRows(),
        defaultView.hasMore(),
        defaultView.moreCount(),
        defaultView.moreBarLeft(),
        defaultView.moreBarWidth(),
        defaultView.extraBars(),
        views,
        defaultView.rowCount(),
        defaultView.trackHeightRpx(),
        defaultView.visibleCount()
    );
  }

  private int computeSheetWidth(List<LaneSeed> laneSeeds, int startYear, int endYear) {
    int span = Math.max(1, endYear - startYear);
    int width = SHEET_WIDTH_RPX;
    for (int pass = 0; pass < 2; pass++) {
      int maxRows = 1;
      for (LaneSeed seed : laneSeeds) {
        UnitSwimMatrixDTO.LaneView view = SwimLaneLayout
            .buildPriorityViews(seed.bars(), startYear, span, width)
            .get("p3");
        maxRows = Math.max(maxRows, view.rowCount());
      }
      double factor = Math.max(0.5, Math.min(4.0, maxRows / 5.0));
      width = (int) Math.round(SHEET_WIDTH_RPX * factor);
    }
    return width;
  }

  private static String laneIcon(String key) {
    return switch (key) {
      case "junji" -> "王";
      case "zongqi" -> "宗";
      case "wenchen" -> "文";
      case "wujiang" -> "武";
      case "shilue" -> "事";
      case "dianzhi" -> "制";
      case "lunzhu" -> "论";
      case "huanguan" -> "宦";
      case "shuzhong" -> "民";
      case "fanzhu" -> "蕃";
      default -> "史";
    };
  }

  private List<UnitSwimMatrixDTO.AxisTick> buildTicks(int start, int end) {
    int span = Math.max(1, end - start);
    int step = span <= 20 ? 5 : span <= 80 ? 10 : span <= 200 ? 25 : 50;
    List<UnitSwimMatrixDTO.AxisTick> ticks = new ArrayList<>();
    int first = ((start / step) + (start % step == 0 ? 0 : 1)) * step;
    if (first < start) first += step;
    for (int y = first; y < end; y += step) {
      double left = pct(y, start, span);
      ticks.add(new UnitSwimMatrixDTO.AxisTick(fmtAxisYear(y), fmtPct(left)));
    }
    return ticks;
  }

  private List<String> loadConcurrentItems(String civName, String dynastyName, int start, int end) {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT DISTINCT COALESCE(NULLIF(TRIM(r.civilization_name),''), c.display_name) AS civ, "
            + "COALESCE(NULLIF(TRIM(r.name),''), r.dynasty_name) AS title "
            + "FROM historical_regime r "
            + "JOIN civilization_l1 c ON c.id=r.civilization_l1_id "
            + "WHERE r.status=1 AND r.start_year IS NOT NULL AND r.end_year IS NOT NULL "
            + "AND r.start_year<? AND r.end_year>? "
            + "LIMIT 24",
        end,
        start
    );
    List<String> out = new ArrayList<>();
    String self = civName + "·" + dynastyName;
    out.add(self);
    for (Map<String, Object> r : rows) {
      String item = r.get("civ") + "·" + r.get("title");
      if (!out.contains(item)) out.add(item);
    }
    return out;
  }

  private static double pct(int year, int start, int span) {
    return Math.max(0, Math.min(100, 100.0 * (year - start) / span));
  }

  private static String fmtPct(double v) {
    return String.format("%.2f%%", v);
  }

  private static String fmtAxisYear(int y) {
    if (y < 0) return "-" + Math.abs(y);
    return String.valueOf(y);
  }

  /** P0 最高优先级；优先使用 priority_code，importance_level 仅作历史数据兜底。 */
  private static String priority(Object priorityCode, Object imp) {
    if (priorityCode != null) {
      String code = String.valueOf(priorityCode).trim().toLowerCase();
      if (List.of("p0", "p1", "p2", "p3").contains(code)) {
        return code;
      }
    }
    int v = imp == null ? 2 : ((Number) imp).intValue();
    if (v <= 0) return "p0";
    if (v == 1) return "p1";
    if (v == 2) return "p2";
    return "p3";
  }

  private record LaneSeed(BoxCategorySupport.CategoryDef def, List<SwimLaneLayout.SwimBarInput> bars) {}
}
