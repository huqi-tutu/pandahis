package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitCivTabsDTO;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitHeroDTO;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitMatrixDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class UnitService {
  /** PRD V1.1：君纪 → 士臣 → 典制 → 事略 → 民录 */
  private static final List<UnitMatrixDTO.Category> CATEGORIES = List.of(
      new UnitMatrixDTO.Category("junji", "君纪"),
      new UnitMatrixDTO.Category("shichen", "士臣"),
      new UnitMatrixDTO.Category("dianzhi", "典制"),
      new UnitMatrixDTO.Category("shilue", "事略"),
      new UnitMatrixDTO.Category("minlu", "民录"),
      new UnitMatrixDTO.Category("lunzhu", "论著")
  );

  private final JdbcTemplate jdbcTemplate;
  private final UnitDynastyResolver dynastyResolver;

  public UnitService(
      JdbcTemplate jdbcTemplate,
      UnitDynastyResolver dynastyResolver
  ) {
    this.jdbcTemplate = jdbcTemplate;
    this.dynastyResolver = dynastyResolver;
  }

  public UnitHeroDTO loadHero(String unitId) {
    Optional<String> dynastyId = dynastyResolver.resolveDynastyId(unitId);
    if (dynastyId.isPresent()) {
      return loadDynastyHero(dynastyId.get());
    }
    throw ApiException.notFound("unit not found");
  }

  private UnitHeroDTO loadDynastyHero(String dynastyId) {
    Map<String, Object> row = dynastyResolver.requireDynastyById(dynastyId);
    String civName = dynastyResolver.civilizationName(row);
    String dynastyName = Optional.ofNullable((String) row.get("name")).orElse("").trim();
    String crumb = joinNonBlank(" · ", civName, dynastyName.isEmpty() ? null : dynastyName);

    int startYear = dynastyResolver.dynastyStartYear(row);
    int endYear = dynastyResolver.dynastyEndYear(row);
    int duration = Math.max(0, endYear - startYear);

    String summary = resolveDynastySummary(dynastyId);

    UnitHeroDTO.Unit unit = new UnitHeroDTO.Unit(
        dynastyId,
        dynastyName,
        null,
        dynastyName,
        crumb,
        null,
        null,
        null,
        startYear,
        endYear,
        duration,
        summary,
        ""
    );

    List<UnitHeroDTO.CategoryTip> tips = categoryTips();

    long civId = ((Number) row.get("civilization_l1_id")).longValue();
    List<UnitHeroDTO.RelatedUnit> related = jdbcTemplate.query(
        "SELECT id, name AS title, start_year FROM historical_dynasty "
            + "WHERE status=1 AND id<>? AND civilization_l1_id<>? "
            + "AND start_year IS NOT NULL "
            + "ORDER BY ABS(start_year - ?) ASC, id ASC LIMIT 12",
        (rs, i) -> new UnitHeroDTO.RelatedUnit(
            rs.getString("id"),
            rs.getString("title"),
            rs.getInt("start_year")
        ),
        dynastyId,
        civId,
        startYear
    );

    List<UnitHeroDTO.NextUnit> nextRows = jdbcTemplate.query(
        "SELECT id, name AS title, start_year FROM historical_dynasty "
            + "WHERE status=1 AND civilization_l1_id=? AND id<>? AND start_year>=? "
            + "ORDER BY start_year ASC, id ASC LIMIT 1",
        (rs, i) -> new UnitHeroDTO.NextUnit(
            rs.getString("id"),
            rs.getString("title"),
            rs.getInt("start_year")
        ),
        civId,
        dynastyId,
        endYear
    );
    UnitHeroDTO.NextUnit next = nextRows.isEmpty() ? null : nextRows.get(0);

    return new UnitHeroDTO(unit, tips, related, next);
  }

  private String resolveDynastySummary(String dynastyId) {
    try {
      String summary = jdbcTemplate.queryForObject(
          "SELECT summary FROM historical_dynasty WHERE id=? AND status=1",
          String.class,
          dynastyId
      );
      if (summary != null && !summary.isBlank()) {
        return summary.trim();
      }
    } catch (Exception ignored) {
      // summary 列可能尚未迁移
    }
    return "空";
  }

  private static List<UnitHeroDTO.CategoryTip> categoryTips() {
    return List.of(
        new UnitHeroDTO.CategoryTip("junji", "君纪", "帝王本纪、君主世系、登基册立……"),
        new UnitHeroDTO.CategoryTip("shichen", "士臣", "将相列传、名臣政绩、文人士大夫……"),
        new UnitHeroDTO.CategoryTip("dianzhi", "典制", "制度、礼法、官制、财政、军制……"),
        new UnitHeroDTO.CategoryTip("shilue", "事略", "重要事件、战争、外交、灾异与节点……"),
        new UnitHeroDTO.CategoryTip("minlu", "民录", "社会民生、风俗、群体生活与变迁……"),
        new UnitHeroDTO.CategoryTip("lunzhu", "论著", "学术论著、思想文献与评论……")
    );
  }

  public UnitMatrixDTO loadMatrix(String unitId) {
    String dynastyId = dynastyResolver.resolveDynastyId(unitId)
        .orElseThrow(() -> ApiException.notFound("unit not found"));
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT id,title,category_key,start_year,importance_level,blurb "
            + "FROM historical_box WHERE dynasty_id=? AND status=1",
        dynastyId
    );
    return buildMatrixFromRows(rows);
  }

  public UnitCivTabsDTO loadCivTabs(String unitId) {
    Map<String, Object> row = dynastyResolver.requireDynastyRow(unitId);
    long civId = ((Number) row.get("civilization_l1_id")).longValue();
    String civName = dynastyResolver.civilizationName(row);
    String dynastyId = (String) row.get("id");
    return new UnitCivTabsDTO(List.of(new UnitCivTabsDTO.Tab(civId, civName, dynastyId, true)));
  }

  private UnitMatrixDTO buildMatrixFromRows(List<Map<String, Object>> rows) {
    SortedSet<Integer> years = new TreeSet<>();
    for (Map<String, Object> r : rows) {
      Object y = r.get("start_year");
      if (y != null) years.add(((Number) y).intValue());
    }

    List<UnitMatrixDTO.YearItem> yearItems = years.stream()
        .map(y -> new UnitMatrixDTO.YearItem(y, yearLabel(y)))
        .collect(Collectors.toList());

    record Key(int year, String category) {}
    Map<Key, Map<String, Object>> best = new HashMap<>();
    for (Map<String, Object> r : rows) {
      Object yObj = r.get("start_year");
      if (yObj == null) continue;
      int year = ((Number) yObj).intValue();
      String cat = (String) r.get("category_key");
      if (cat == null) continue;

      Key k = new Key(year, cat);
      Map<String, Object> current = best.get(k);
      if (current == null) {
        best.put(k, r);
        continue;
      }
      int curImportance = importance(current.get("importance_level"));
      int newImportance = importance(r.get("importance_level"));
      if (newImportance < curImportance) {
        best.put(k, r);
        continue;
      }
      if (newImportance == curImportance) {
        String curId = (String) current.get("id");
        String newId = (String) r.get("id");
        if (newId != null && (curId == null || newId.compareTo(curId) < 0)) {
          best.put(k, r);
        }
      }
    }

    List<UnitMatrixDTO.Item> items = best.values().stream()
        .map(r -> {
          int year = ((Number) r.get("start_year")).intValue();
          int imp = importance(r.get("importance_level"));
          boolean highlight = imp <= 1;
          String blurb = Optional.ofNullable((String) r.get("blurb")).orElse("").trim();
          return new UnitMatrixDTO.Item(
              (String) r.get("id"),
              year,
              (String) r.get("category_key"),
              (String) r.get("title"),
              blurb.isEmpty() ? null : blurb,
              highlight
          );
        })
        .sorted(Comparator.comparing(UnitMatrixDTO.Item::year)
            .thenComparing(UnitMatrixDTO.Item::categoryKey))
        .toList();

    return new UnitMatrixDTO(yearItems, CATEGORIES, items);
  }

  private static String yearLabel(int year) {
    return year < 0 ? ("前" + Math.abs(year)) : String.valueOf(year);
  }

  private static int importance(Object v) {
    if (v == null) return 0;
    return ((Number) v).intValue();
  }

  private static String joinNonBlank(String sep, String... parts) {
    return Arrays.stream(parts)
        .filter(Objects::nonNull)
        .map(String::trim)
        .filter(s -> !s.isEmpty())
        .collect(Collectors.joining(sep));
  }
}

