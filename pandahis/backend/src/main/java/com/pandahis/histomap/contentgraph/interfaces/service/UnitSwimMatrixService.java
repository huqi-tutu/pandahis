package com.pandahis.histomap.contentgraph.interfaces.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class UnitSwimMatrixService {
  private static final ObjectMapper OM = new ObjectMapper();
  private static final int MAX_VISIBLE = 10;
  private static final int SHEET_WIDTH_RPX = 1440;

  private static final List<LaneDef> LANES = List.of(
      new LaneDef("junji", "君纪", "#F1A805", "continuous"),
      new LaneDef("shichen", "士臣", "#E0C088", "shichen"),
      new LaneDef("dianzhi", "典制", "#92ADA4", "continuous"),
      new LaneDef("shilue", "事略", "#B3D9E0", "continuous"),
      new LaneDef("minlu", "民录", "#EDD5C0", "isolated")
  );

  private static final Map<String, String> LANE_BORDER = Map.of(
      "junji", "#F1A805",
      "shichen", "#E0C088",
      "dianzhi", "#92ADA4",
      "shilue", "#B3D9E0",
      "minlu", "#EDD5C0"
  );

  private final JdbcTemplate jdbcTemplate;

  public UnitSwimMatrixService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public UnitSwimMatrixDTO load(String unitId) {
    List<Map<String, Object>> unitRows = jdbcTemplate.queryForList(
        "SELECT id, name, dynasty_name, civilization_l1_id, start_year, end_year FROM historical_unit "
            + "WHERE id=? AND status=1",
        unitId
    );
    if (unitRows.isEmpty()) {
      throw ApiException.notFound("unit not found");
    }
    Map<String, Object> unit = unitRows.get(0);
    int startYear = ((Number) unit.get("start_year")).intValue();
    int endYear = ((Number) unit.get("end_year")).intValue();
    if (endYear <= startYear) endYear = startYear + 1;
    String dynastyName = Optional.ofNullable((String) unit.get("dynasty_name")).orElse("").trim();
    String civName = jdbcTemplate.queryForObject(
        "SELECT display_name FROM civilization_l1 WHERE id=?",
        String.class,
        ((Number) unit.get("civilization_l1_id")).longValue()
    );
    if (civName == null) civName = "";

    List<Map<String, Object>> boxes = jdbcTemplate.queryForList(
        "SELECT id, title, category_key, start_year, end_year, importance_level, blurb "
            + "FROM historical_box WHERE unit_id=? AND status=1 ORDER BY start_year ASC, id ASC",
        unitId
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
    List<List<BarInput>> packed = new ArrayList<>();
    for (BarInput b : bars) {
      boolean placed = false;
      for (List<BarInput> row : packed) {
        if (!overlaps(row, b)) {
          row.add(b);
          placed = true;
          break;
        }
      }
      if (!placed) {
        List<BarInput> row = new ArrayList<>();
        row.add(b);
        packed.add(row);
      }
    }

    List<List<UnitSwimMatrixDTO.Bar>> out = new ArrayList<>();
    for (List<BarInput> row : packed) {
      List<UnitSwimMatrixDTO.Bar> rowOut = new ArrayList<>();
      for (BarInput b : row) {
        rowOut.add(toBar(b, layout, startYear, span));
      }
      out.add(rowOut);
    }
    return out.isEmpty() ? List.of(List.of()) : out;
  }

  private static boolean overlaps(List<BarInput> row, BarInput b) {
    for (BarInput x : row) {
      if (b.start < x.end && b.end > x.start) return true;
    }
    return false;
  }

  private UnitSwimMatrixDTO.Bar toBar(BarInput b, String layout, int startYear, int span) {
    double left = pct(b.start, startYear, span);
    double right = pct(b.end, startYear, span);
    double width = Math.max(2, right - left);
    String leftStr = fmtPct(left);
    String widthStr = fmtPct(width);
    String timeRange = fmtYear(b.start) + " — " + fmtYear(b.end);
    String pri = b.priority;

    if ("shichen".equals(layout) || "continuous".equals(layout)) {
      double chipW = Math.min(width * 0.55, 18);
      double chipL = left + (width - chipW) / 2;
      return new UnitSwimMatrixDTO.Bar(
          b.title,
          b.boxId,
          b.boxId,
          b.title,
          leftStr,
          widthStr,
          leftStr,
          widthStr,
          fmtPct(chipL),
          fmtPct(chipW),
          fmtPct(Math.max(0, chipL - left)),
          fmtPct(chipL + chipW),
          fmtPct(Math.max(0, right - chipL - chipW)),
          pri,
          "default",
          10,
          timeRange
      );
    }

    return new UnitSwimMatrixDTO.Bar(
        b.title,
        b.boxId,
        b.boxId,
        b.title,
        leftStr,
        widthStr,
        leftStr,
        widthStr,
        leftStr,
        widthStr,
        "0%",
        leftStr,
        widthStr,
        pri,
        "default",
        10,
        timeRange
    );
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
        "SELECT DISTINCT c.display_name AS civ, COALESCE(NULLIF(TRIM(u.dynasty_name),''), u.name) AS title, "
            + "u.start_year, u.end_year FROM historical_unit u "
            + "JOIN civilization_l1 c ON c.id=u.civilization_l1_id "
            + "WHERE u.status=1 AND u.start_year<? AND u.end_year>? "
            + "ORDER BY u.start_year ASC LIMIT 24",
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

  private static String priority(Object imp) {
    int v = imp == null ? 2 : ((Number) imp).intValue();
    if (v >= 4) return "p0";
    if (v >= 3) return "p1";
    if (v >= 2) return "p2";
    return "p3";
  }

  private record LaneDef(String key, String label, String borderColor, String layout) {}

  private record BarInput(String boxId, String title, int start, int end, String priority) {}
}
