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
      new UnitMatrixDTO.Category("minlu", "民录")
  );

  private final JdbcTemplate jdbcTemplate;
  private final UnitCardImageResolver unitCardImageResolver;

  public UnitService(JdbcTemplate jdbcTemplate, UnitCardImageResolver unitCardImageResolver) {
    this.jdbcTemplate = jdbcTemplate;
    this.unitCardImageResolver = unitCardImageResolver;
  }

  public UnitHeroDTO loadHero(String unitId) {
    List<Map<String, Object>> heroRows = jdbcTemplate.queryForList(
        "SELECT id,name,ruler_name,dynasty_name,era_name,temple_name,era_title,civilization_l1_id,start_year,end_year,"
            + "duration_years,summary,card_image_url FROM historical_unit WHERE id=? AND status=1",
        unitId
    );
    if (heroRows.isEmpty()) {
      throw ApiException.notFound("unit not found");
    }
    Map<String, Object> row = heroRows.get(0);

    Long civId = ((Number) row.get("civilization_l1_id")).longValue();
    String civName = jdbcTemplate.queryForObject(
        "SELECT display_name FROM civilization_l1 WHERE id=?",
        String.class,
        civId
    );
    if (civName == null) civName = "";

    String dynastyRaw = (String) row.get("dynasty_name");
    String dynasty = dynastyRaw == null ? "" : dynastyRaw.trim();
    String crumb = joinNonBlank(" · ", civName, dynasty.isEmpty() ? null : dynasty);

    String era = (String) row.get("era_name");
    String eraText = (era == null || era.isBlank()) ? null : ("年号 " + era);

    int startYear = ((Number) row.get("start_year")).intValue();
    int endYear = ((Number) row.get("end_year")).intValue();

    String cardImageUrl = unitCardImageResolver.resolveForUnit(
        unitId,
        (String) row.get("card_image_url")
    );
    if (cardImageUrl == null) {
      cardImageUrl = "";
    }

    String rulerName = Optional.ofNullable((String) row.get("ruler_name")).orElse("").trim();
    String templeName = Optional.ofNullable((String) row.get("temple_name")).orElse("").trim();
    String eraTitle = Optional.ofNullable((String) row.get("era_title")).orElse("").trim();

    UnitHeroDTO.Unit unit = new UnitHeroDTO.Unit(
        (String) row.get("id"),
        (String) row.get("name"),
        rulerName.isEmpty() ? null : rulerName,
        dynasty,
        crumb,
        eraText,
        templeName.isEmpty() ? null : templeName,
        eraTitle.isEmpty() ? null : eraTitle,
        startYear,
        endYear,
        ((Number) row.get("duration_years")).intValue(),
        Optional.ofNullable((String) row.get("summary")).orElse(""),
        cardImageUrl
    );

    List<UnitHeroDTO.CategoryTip> tips = List.of(
        new UnitHeroDTO.CategoryTip("junji", "君纪", "帝王本纪、君主世系、登基册立……"),
        new UnitHeroDTO.CategoryTip("shichen", "士臣", "将相列传、名臣政绩、文人士大夫……"),
        new UnitHeroDTO.CategoryTip("dianzhi", "典制", "制度、礼法、官制、财政、军制……"),
        new UnitHeroDTO.CategoryTip("shilue", "事略", "重要事件、战争、外交、灾异与节点……"),
        new UnitHeroDTO.CategoryTip("minlu", "民录", "社会民生、风俗、群体生活与变迁……")
    );

    List<UnitHeroDTO.RelatedUnit> related = jdbcTemplate.query(
        "SELECT id, COALESCE(NULLIF(TRIM(dynasty_name),''), name) AS title, start_year FROM historical_unit "
            + "WHERE status=1 AND id<>? AND civilization_l1_id<>? ORDER BY ABS(start_year - ?) ASC, id ASC LIMIT 12",
        (rs, i) -> new UnitHeroDTO.RelatedUnit(
            rs.getString("id"),
            rs.getString("title"),
            rs.getInt("start_year")
        ),
        unitId,
        civId,
        startYear
    );

    List<UnitHeroDTO.NextUnit> nextRows = jdbcTemplate.query(
        "SELECT id, COALESCE(NULLIF(TRIM(dynasty_name),''), name) AS title, start_year FROM historical_unit "
            + "WHERE status=1 AND civilization_l1_id=? AND id<>? AND start_year>=? ORDER BY start_year ASC, id ASC LIMIT 1",
        (rs, i) -> new UnitHeroDTO.NextUnit(
            rs.getString("id"),
            rs.getString("title"),
            rs.getInt("start_year")
        ),
        civId,
        unitId,
        endYear
    );
    UnitHeroDTO.NextUnit next = nextRows.isEmpty() ? null : nextRows.get(0);

    return new UnitHeroDTO(unit, tips, related, next);
  }

  public UnitMatrixDTO loadMatrix(String unitId) {
    // ensure unit exists
    Integer exists = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM historical_unit WHERE id=? AND status=1",
        Integer.class,
        unitId
    );
    if (exists == null || exists == 0) {
      throw ApiException.notFound("unit not found");
    }

    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT id,title,category_key,start_year,importance_level,blurb " +
            "FROM historical_box WHERE unit_id=? AND status=1",
        unitId
    );

    // years
    SortedSet<Integer> years = new TreeSet<>();
    for (Map<String, Object> r : rows) {
      Object y = r.get("start_year");
      if (y != null) years.add(((Number) y).intValue());
    }

    List<UnitMatrixDTO.YearItem> yearItems = years.stream()
        .map(y -> new UnitMatrixDTO.YearItem(y, yearLabel(y)))
        .collect(Collectors.toList());

    // pick best per (year,category)
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
      if (newImportance > curImportance) {
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
          boolean highlight = imp >= 4;
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

  public UnitCivTabsDTO loadCivTabs(String unitId) {
    List<Map<String, Object>> unitRows = jdbcTemplate.queryForList(
        "SELECT id,civilization_l1_id,start_year,end_year FROM historical_unit WHERE id=? AND status=1",
        unitId
    );
    if (unitRows.isEmpty()) {
      throw ApiException.notFound("unit not found");
    }
    Map<String, Object> unit = unitRows.get(0);
    long civId = ((Number) unit.get("civilization_l1_id")).longValue();
    String civName = jdbcTemplate.queryForObject(
        "SELECT display_name FROM civilization_l1 WHERE id=?",
        String.class,
        civId
    );
    if (civName == null) civName = "";
    return new UnitCivTabsDTO(List.of(new UnitCivTabsDTO.Tab(civId, civName, unitId, true)));
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

