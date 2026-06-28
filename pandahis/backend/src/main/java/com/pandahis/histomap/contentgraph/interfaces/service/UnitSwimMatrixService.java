package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class UnitSwimMatrixService {
  private static final int MAX_VISIBLE = 10;
  private static final int SHEET_WIDTH_RPX = 1440;

  private static final List<LaneDef> LANES = List.of(
      new LaneDef("junji", "君纪", "#F1A805", "continuous"),
      new LaneDef("shichen", "士臣", "#E0C088", "shichen"),
      new LaneDef("dianzhi", "典制", "#92ADA4", "continuous"),
      new LaneDef("shilue", "事略", "#B3D9E0", "continuous"),
      new LaneDef("minlu", "民录", "#EDD5C0", "isolated"),
      new LaneDef("lunzhu", "论著", "#A894B8", "isolated")
  );

  private static final Map<String, String> LANE_BORDER = Map.of(
      "junji", "#F1A805",
      "shichen", "#E0C088",
      "dianzhi", "#92ADA4",
      "shilue", "#B3D9E0",
      "minlu", "#EDD5C0",
      "lunzhu", "#A894B8"
  );

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
        "SELECT id, title, category_key, start_year, end_year, importance_level, blurb "
            + "FROM historical_box WHERE dynasty_id=? AND status=1 "
            + "ORDER BY start_year ASC, id ASC",
        dynastyId
    );

    List<UnitSwimMatrixDTO.AxisTick> ticks = buildTicks(startYear, endYear);
    String endLabel = fmtAxisYear(endYear);

    List<UnitSwimMatrixDTO.Lane> lanes = new ArrayList<>();
    for (LaneDef def : LANES) {
      List<BarInput> bars = new ArrayList<>();
      for (Map<String, Object> b : boxes) {
        String cat = (String) b.get("category_key");
        if (cat == null || !cat.equals(def.key())) continue;
        int bs = b.get("start_year") == null ? startYear : ((Number) b.get("start_year")).intValue();
        int be = b.get("end_year") == null ? bs : ((Number) b.get("end_year")).intValue();
        if (be <= bs) be = bs + 1;
        bars.add(new BarInput(
            (String) b.get("id"),
            (String) b.get("title"),
            bs,
            be,
            priority(b.get("importance_level"))
        ));
      }
      lanes.add(buildLane(def, bars, startYear, endYear));
    }

    List<String> concurrent = loadConcurrentItems(civName, dynastyName, startYear, endYear);

    return new UnitSwimMatrixDTO(
        startYear,
        endYear,
        endLabel,
        ticks,
        lanes,
        concurrent,
        SHEET_WIDTH_RPX
    );
  }

  private UnitSwimMatrixDTO.Lane buildLane(LaneDef def, List<BarInput> bars, int startYear, int endYear) {
    int span = Math.max(1, endYear - startYear);
    boolean hasMore = bars.size() > MAX_VISIBLE;
    List<BarInput> visible = hasMore ? bars.subList(0, MAX_VISIBLE) : bars;
    int moreCount = hasMore ? bars.size() - MAX_VISIBLE : 0;

    List<List<UnitSwimMatrixDTO.Bar>> rows = packBars(visible, def.layout(), startYear, span);

    String moreBarLeft = "0%";
    String moreBarWidth = "12%";
    if (hasMore && !visible.isEmpty()) {
      BarInput last = visible.get(visible.size() - 1);
      double left = pct(last.end, startYear, span);
      moreBarLeft = fmtPct(Math.min(88, left));
      moreBarWidth = "12%";
    }

    return new UnitSwimMatrixDTO.Lane(
        def.label(),
        LANE_BORDER.getOrDefault(def.key(), "#84572F"),
        def.layout(),
        rows,
        hasMore,
        moreCount,
        moreBarLeft,
        moreBarWidth
    );
  }

  private List<List<UnitSwimMatrixDTO.Bar>> packBars(
      List<BarInput> bars,
      String layout,
      int startYear,
      int span
  ) {
    List<SwimLaneLayout.SwimBarInput> inputs = bars.stream()
        .map(b -> new SwimLaneLayout.SwimBarInput(b.boxId(), b.title(), b.start(), b.end(), b.priority()))
        .toList();
    return switch (layout) {
      case "shichen" -> SwimLaneLayout.packShichen(inputs, startYear, span);
      case "isolated" -> SwimLaneLayout.packIsolated(inputs, startYear, span);
      default -> SwimLaneLayout.packContinuous(inputs, startYear, span);
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

  private static String fmtYear(int y) {
    if (y < 0) return "前" + Math.abs(y);
    return String.valueOf(y);
  }

  /** P0=0 最高优先级 → p0；与 import_box_index_json 一致 */
  private static String priority(Object imp) {
    int v = imp == null ? 2 : ((Number) imp).intValue();
    if (v <= 0) return "p0";
    if (v == 1) return "p1";
    if (v == 2) return "p2";
    return "p3";
  }

  private record LaneDef(String key, String label, String borderColor, String layout) {}

  private record BarInput(String boxId, String title, int start, int end, String priority) {}
}
