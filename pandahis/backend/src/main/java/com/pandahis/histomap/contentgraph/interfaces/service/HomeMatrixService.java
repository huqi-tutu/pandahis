package com.pandahis.histomap.contentgraph.interfaces.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.interfaces.dto.HomeMatrixDTO;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.Set;
import java.util.TreeSet;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class HomeMatrixService {
  private static final ObjectMapper OM = new ObjectMapper();
  private static final int SLICE_MIN_H = 48;
  private static final int SLICE_MAX_H = 120;
  private static final int YEAR_LABEL_GAP = 72;

  private static final String[] ERA_COLORS = {
      "#B3A08F", "#F8D180", "#F9E9D0", "#C0D6CF", "#D9EBEF", "#F6EAE0"
  };

  private final JdbcTemplate jdbcTemplate;

  public HomeMatrixService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public HomeMatrixDTO load(long civId) {
    return load(civId, Set.of());
  }

  public HomeMatrixDTO load(long civId, Set<String> expandedDynastyKeys) {
    List<Map<String, Object>> units = jdbcTemplate.queryForList(
        "SELECT id, name, dynasty_name, dynasty_id, enthronement_year, abdication_year, reign_duration, tags "
            + "FROM historical_emperor WHERE status=1 AND civilization_l1_id=? ORDER BY enthronement_year ASC, id ASC",
        civId
    );
    if (units.isEmpty()) {
      return new HomeMatrixDTO(List.of(), List.of(), List.of(), 0);
    }

    List<Entry> entries = new ArrayList<>();
    int colorIdx = 0;
    Map<String, Integer> dynastyCounts = new HashMap<>();
    for (Map<String, Object> u : units) {
      String dynastyId = trimOrEmpty((String) u.get("dynasty_id"));
      if (!dynastyId.isEmpty()) {
        dynastyCounts.merge(dynastyId, 1, Integer::sum);
      }
    }

    for (Map<String, Object> u : units) {
      int start = u.get("enthronement_year") == null ? 0 : ((Number) u.get("enthronement_year")).intValue();
      int end = u.get("abdication_year") == null ? start + 1 : ((Number) u.get("abdication_year")).intValue();
      if (end <= start) end = start + 1;
      String dynasty = trimOrEmpty((String) u.get("dynasty_name"));
      String dynastyId = trimOrEmpty((String) u.get("dynasty_id"));
      String dynastyKey = !dynastyId.isEmpty() ? dynastyId : slugDynasty(dynasty);
      String title = trimOrEmpty((String) u.get("name"));
      List<String> highlights = parseHighlights((String) u.get("tags"));
      entries.add(new Entry(
          (String) u.get("id"),
          title,
          dynasty.isEmpty() ? title : dynasty,
          dynastyId,
          dynastyKey,
          start,
          end,
          fmtRange(start, end),
          ERA_COLORS[colorIdx % ERA_COLORS.length],
          highlights
      ));
      colorIdx++;
    }

    TreeSet<Integer> boundaries = new TreeSet<>();
    for (Entry e : entries) {
      boundaries.add(e.start);
      boundaries.add(e.end);
    }
    List<Integer> times = new ArrayList<>(boundaries);

    List<Slice> slices = new ArrayList<>();
    for (int i = 0; i < times.size() - 1; i++) {
      int tS = times.get(i);
      int tE = times.get(i + 1);
      if (tE <= tS) continue;
      List<Entry> active = entries.stream()
          .filter(e -> e.start <= tS && e.end > tS)
          .sorted(Comparator.comparingInt((Entry e) -> e.start).thenComparing(e -> e.unitId))
          .toList();
      if (active.isEmpty()) continue;
      slices.add(new Slice(tS, tE, active));
    }

    int y = 0;
    List<HomeMatrixDTO.Row> rows = new ArrayList<>();
    List<SliceLayout> layouts = new ArrayList<>();
    int lastYearY = -YEAR_LABEL_GAP;
    String lastHxDynastyKey = "";

    for (int i = 0; i < slices.size(); i++) {
      Slice sl = slices.get(i);
      int span = Math.max(1, sl.tE - sl.tS);
      int h = Math.min(SLICE_MAX_H, Math.max(SLICE_MIN_H, span / 8 + SLICE_MIN_H));
      boolean showYear = y - lastYearY >= YEAR_LABEL_GAP || i == 0;
      if (showYear) lastYearY = y;

      List<Entry> displayActive = collapseActive(sl.active, expandedDynastyKeys, dynastyCounts);
      List<Placement> placements = assignPlacements(displayActive);
      layouts.add(new SliceLayout(y, h, sl, placements));

      String rowDynastyKey = displayActive.isEmpty() ? "" : displayActive.get(0).dynastyKey;
      String hxLabel = "";
      boolean expandable = false;
      boolean expanded = false;
      if (showYear && !displayActive.isEmpty()) {
        Entry lead = displayActive.get(0);
        if (!lead.dynastyKey.equals(lastHxDynastyKey)) {
          hxLabel = lead.dynasty;
          lastHxDynastyKey = lead.dynastyKey;
          int count = dynastyCounts.getOrDefault(lead.dynastyId, 0);
          if (count == 0 && !lead.dynastyId.isEmpty()) count = dynastyCounts.getOrDefault(lead.dynastyKey, 0);
          expandable = count > 1;
          expanded = expandable && expandedDynastyKeys.contains(lead.dynastyKey);
          rowDynastyKey = lead.dynastyKey;
        }
      }

      rows.add(new HomeMatrixDTO.Row(
          "row_" + sl.tS + "_" + i,
          y,
          h,
          fmtTimelineYear(sl.tS),
          hxLabel,
          showYear,
          expandable,
          expanded,
          rowDynastyKey
      ));
      y += h;
    }

    List<HomeMatrixDTO.Block> blocks = new ArrayList<>();
    List<HomeMatrixDTO.Overlay> overlays = new ArrayList<>();

    for (SliceLayout sl : layouts) {
      int n = sl.placements.size();
      for (int pi = 0; pi < n; pi++) {
        Placement p = sl.placements.get(pi);
        Entry e = p.entry;
        double leftPct = (100.0 * pi) / n;
        double widthPct = 100.0 / n;
        String blockId = e.unitId + "_" + sl.slice.tS;

        blocks.add(new HomeMatrixDTO.Block(
            blockId,
            sl.y,
            sl.h,
            leftPct,
            widthPct,
            e.cardBg,
            e.title,
            e.dynasty,
            "",
            e.start,
            e.unitId,
            n <= 1 ? "single" : "group",
            n <= 1 ? e.title : e.dynasty,
            e.timeRange,
            "8rpx",
            pi == 0 ? "edge-left" : (pi == n - 1 ? "edge-right" : ""),
            "",
            false,
            false,
            false,
            false,
            false,
            ""
        ));

        String labelLayout = n <= 1 ? "inline" : "stacked";
        List<HomeMatrixDTO.HighlightTag> tags = e.highlights.stream()
            .limit(2)
            .map(t -> new HomeMatrixDTO.HighlightTag(t, "background-color:#B0A89E;border:none;"))
            .toList();

        overlays.add(new HomeMatrixDTO.Overlay(
            blockId + "_ovl",
            sl.y + 8,
            leftPct,
            widthPct,
            sl.y + sl.h - 28,
            leftPct,
            widthPct,
            24,
            "br",
            18,
            labelLayout,
            n <= 1 ? "single" : "group",
            e.title,
            n <= 1 ? e.title : e.dynasty,
            e.timeRange,
            false,
            tags.isEmpty(),
            false,
            tags
        ));
      }
    }

    return new HomeMatrixDTO(rows, blocks, overlays, y);
  }

  private static List<Entry> collapseActive(
      List<Entry> active,
      Set<String> expandedDynastyKeys,
      Map<String, Integer> dynastyCounts
  ) {
    LinkedHashMap<String, Entry> merged = new LinkedHashMap<>();
    List<Entry> out = new ArrayList<>();
    for (Entry e : active) {
      int count = dynastyCounts.getOrDefault(e.dynastyId, 0);
      boolean collapsible = count > 1 && !expandedDynastyKeys.contains(e.dynastyKey);
      if (!collapsible) {
        out.add(e);
        continue;
      }
      merged.merge(e.dynastyKey, e, HomeMatrixService::mergeDynastyEntry);
    }
    out.addAll(merged.values());
    out.sort(Comparator.comparingInt((Entry e) -> e.start).thenComparing(e -> e.unitId));
    return out;
  }

  private static Entry mergeDynastyEntry(Entry a, Entry b) {
    int start = Math.min(a.start, b.start);
    int end = Math.max(a.end, b.end);
    return new Entry(
        a.unitId,
        a.dynasty,
        a.dynasty,
        a.dynastyId,
        a.dynastyKey,
        start,
        end,
        fmtRange(start, end),
        a.cardBg,
        a.highlights
    );
  }

  private static String slugDynasty(String dynasty) {
    String d = trimOrEmpty(dynasty);
    if (d.isEmpty()) return "unknown";
    return "dyn_" + d.replaceAll("\\s+", "_");
  }

  private static List<Placement> assignPlacements(List<Entry> active) {
    List<Placement> out = new ArrayList<>();
    for (Entry e : active) {
      out.add(new Placement(e));
    }
    return out;
  }

  private static String fmtTimelineYear(int y) {
    if (y < 0) return "-" + Math.abs(y);
    if (y == 0) return "0";
    return String.valueOf(y);
  }

  private static String fmtRange(int start, int end) {
    return fmtYear(start) + " — " + fmtYear(end);
  }

  private static String fmtYear(int y) {
    if (y < 0) return "前" + Math.abs(y);
    return String.valueOf(y);
  }

  private static String trimOrEmpty(String s) {
    return s == null ? "" : s.trim();
  }

  private static List<String> parseHighlights(String raw) {
    if (raw == null || raw.isBlank()) return List.of();
    String trimmed = raw.trim();
    if (trimmed.startsWith("[")) {
      try {
        JsonNode n = OM.readTree(trimmed);
        if (!n.isArray()) return List.of();
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        for (JsonNode x : n) {
          if (x.isTextual()) {
            String t = x.asText().trim();
            if (!t.isEmpty()) seen.add(t);
          }
          if (seen.size() >= 3) break;
        }
        return List.copyOf(seen);
      } catch (Exception e) {
        return List.of();
      }
    }
    return List.of(trimmed);
  }

  private record Entry(
      String unitId,
      String title,
      String dynasty,
      String dynastyId,
      String dynastyKey,
      int start,
      int end,
      String timeRange,
      String cardBg,
      List<String> highlights
  ) {}

  private record Slice(int tS, int tE, List<Entry> active) {}

  private record Placement(Entry entry) {}

  private record SliceLayout(int y, int h, Slice slice, List<Placement> placements) {}
}
