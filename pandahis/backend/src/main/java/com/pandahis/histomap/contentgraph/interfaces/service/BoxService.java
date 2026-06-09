package com.pandahis.histomap.contentgraph.interfaces.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.config.HistomapProperties;
import com.pandahis.histomap.contentgraph.interfaces.dto.*;
import com.pandahis.histomap.invite.service.DeepTabReadService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class BoxService {
  private final JdbcTemplate jdbcTemplate;
  private final HistomapProperties props;
  private final ObjectMapper objectMapper;
  private final DeepTabReadService deepTabReadService;

  public BoxService(
      JdbcTemplate jdbcTemplate,
      HistomapProperties props,
      ObjectMapper objectMapper,
      DeepTabReadService deepTabReadService
  ) {
    this.jdbcTemplate = jdbcTemplate;
    this.props = props;
    this.objectMapper = objectMapper;
    this.deepTabReadService = deepTabReadService;
  }

  public BoxHeaderDTO loadHeader(String boxId) {
    Map<String, Object> box = findBox(boxId);
    String categoryKey = (String) box.get("category_key");
    int startYear = ((Number) box.get("start_year")).intValue();
    int endYear = ((Number) box.get("end_year")).intValue();

    String unitId = (String) box.get("unit_id");
    Long civId = jdbcTemplate.queryForObject(
        "SELECT civilization_l1_id FROM historical_unit WHERE id=?",
        Long.class,
        unitId
    );
    String civName = civId == null ? "" : Optional.ofNullable(jdbcTemplate.queryForObject(
        "SELECT display_name FROM civilization_l1 WHERE id=?",
        String.class,
        civId
    )).orElse("");

    String subText = yearLabel(startYear) + " · " + civName + " · " + categoryName(categoryKey);
    String blurb = Optional.ofNullable((String) box.get("blurb")).orElse("").trim();

    boolean hasGraphFromDb = exists("SELECT COUNT(1) FROM box_graph_node WHERE box_id=?", boxId);
    Integer unitLinked = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM historical_box b WHERE b.id=? AND b.status=1 AND b.unit_id IS NOT NULL AND TRIM(b.unit_id) <> ''",
        Integer.class,
        boxId
    );
    boolean hasGraph = hasGraphFromDb || (unitLinked != null && unitLinked > 0);
    boolean hasCritiques = exists("SELECT COUNT(1) FROM box_critique WHERE box_id=?", boxId);
    boolean hasRelics = exists("SELECT COUNT(1) FROM box_relic WHERE box_id=?", boxId);
    boolean hasOriginal = parseOriginalRefJson((String) box.get("original_ref_json")) != null;

    var tabSummary = new BoxHeaderDTO.TabSummary(hasGraph, hasCritiques, hasRelics, hasOriginal);

    var access = buildAccess(boxId);
    boolean isFavorite = resolveIsFavorite(boxId);

    return new BoxHeaderDTO(
        new BoxHeaderDTO.Box(
            boxId,
            (String) box.get("title"),
            subText,
            blurb.isEmpty() ? null : blurb,
            categoryKey,
            startYear,
            endYear
        ),
        isFavorite,
        tabSummary,
        access
    );
  }

  private boolean resolveIsFavorite(String boxId) {
    var ctx = UserContextHolder.get();
    if (!ctx.authenticated()) {
      return false;
    }
    Integer n =
        jdbcTemplate.queryForObject(
            "SELECT COUNT(1) FROM user_favorite_box WHERE user_id=? AND box_id=?",
            Integer.class,
            ctx.userId(),
            boxId);
    return n != null && n > 0;
  }

  public BoxDetailDTO loadDetail(String boxId) {
    ensureTabAllowed("detail", boxId);
    Map<String, Object> box = findBox(boxId);
    String detail = Optional.ofNullable((String) box.get("detail_md")).orElse("");
    String flash = Optional.ofNullable((String) box.get("detail_md_flash")).orElse("");
    String pro = Optional.ofNullable((String) box.get("detail_md_pro")).orElse("");
    // 原文见 GET /boxes/{id}/original-ref（消耗阅读数）
    return new BoxDetailDTO(
        detail,
        null,
        flash.isBlank() ? null : flash,
        pro.isBlank() ? null : pro
    );
  }

  public BoxOriginalRefDTO loadOriginalRef(String boxId) {
    ensureDeepTab("original", boxId);
    Map<String, Object> box = findBox(boxId);
    JsonNode ref = parseOriginalRefJson((String) box.get("original_ref_json"));
    return new BoxOriginalRefDTO(ref);
  }

  public BoxGraphDTO loadGraph(String boxId) {
    ensureTabAllowed("graph", boxId);
    Map<String, Object> box = findBox(boxId);
    String boxTitle = Optional.ofNullable((String) box.get("title")).orElse("").trim();

    List<BoxGraphDTO.Node> nodes = jdbcTemplate.query(
        "SELECT node_key,node_type,name,extra_json FROM box_graph_node WHERE box_id=? ORDER BY id ASC",
        (rs, rowNum) -> {
          String extra = rs.getString("extra_json");
          String targetBoxId = null;
          if (extra != null && !extra.isBlank()) {
            try {
              targetBoxId = objectMapper.readTree(extra).path("targetBoxId").asText(null);
            } catch (Exception ignored) {}
          }
          return new BoxGraphDTO.Node(
              rs.getString("node_key"),
              rs.getString("node_type"),
              rs.getString("name"),
              null,
              null,
              targetBoxId,
              extra
          );
        },
        boxId
    );

    List<BoxGraphDTO.Edge> edges = jdbcTemplate.query(
        "SELECT from_node_key,to_node_key,label FROM box_graph_edge WHERE box_id=? ORDER BY id ASC",
        (rs, rowNum) -> new BoxGraphDTO.Edge(
            rs.getString("from_node_key"),
            rs.getString("to_node_key"),
            rs.getString("label")
        ),
        boxId
    );

    if (nodes.isEmpty()) {
      if (boxTitle.contains("黄帝")) {
        return buildHuangDiDemonstrationGraph(boxId);
      }
      var synthetic = syntheticUnitEventGraph(boxId);
      if (synthetic != null) {
        return synthetic;
      }
    }

    if (boxTitle.contains("黄帝") && shouldUseHuangDiDemonstration(nodes)) {
      return buildHuangDiDemonstrationGraph(boxId);
    }

    String centerNodeKey = resolveCenterNodeKey(nodes, boxTitle);
    return new BoxGraphDTO(centerNodeKey, nodes, edges);
  }

  public GraphNodeDetailDTO loadGraphNodeDetail(String boxId, String nodeKey) {
    ensureTabAllowed("graph", boxId);
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT name, node_type, extra_json FROM box_graph_node WHERE box_id=? AND node_key=? LIMIT 1",
        boxId,
        nodeKey
    );
    if (rows.isEmpty()) {
      throw ApiException.notFound("graph node not found");
    }
    Map<String, Object> row = rows.get(0);
    String name = Optional.ofNullable((String) row.get("name")).orElse("").trim();
    String nodeType = Optional.ofNullable((String) row.get("node_type")).orElse("").trim();
    String extra = (String) row.get("extra_json");
    String category = nodeType;
    String role = "";
    String level = "";
    String lineage = "";
    String summary = "";
    String targetBoxId = null;
    if (extra != null && !extra.isBlank()) {
      try {
        JsonNode n = objectMapper.readTree(extra);
        category = textOr(n, "category", category);
        role = textOr(n, "role", role);
        level = textOr(n, "level", level);
        lineage = textOr(n, "lineage", lineage);
        summary = textOr(n, "summary", summary);
        targetBoxId = textOr(n, "targetBoxId", null);
      } catch (Exception ignored) {}
    }
    if (summary.isBlank()) {
      summary = name + " 与当前史略存在「" + (role.isBlank() ? category : role) + "」关联。";
    }
    return new GraphNodeDetailDTO(name, category, role, level, lineage, summary, targetBoxId);
  }

  private static String textOr(JsonNode n, String field, String fallback) {
    JsonNode v = n.get(field);
    if (v == null || v.isNull()) return fallback == null ? "" : fallback;
    return v.asText(fallback == null ? "" : fallback);
  }

  private boolean shouldUseHuangDiDemonstration(List<BoxGraphDTO.Node> nodes) {
    if (nodes.isEmpty() || nodes.size() > 8) return false;
    for (var n : nodes) {
      String key = n.key() == null ? "" : n.key();
      if (key.startsWith("hd_")) return false;
      String extra = n.extraJson() == null ? "" : n.extraJson();
      if (extra.contains("家庭") || extra.contains("师从") || extra.contains("君臣") || extra.contains("敌对")) {
        return false;
      }
    }
    return true;
  }

  private String resolveCenterNodeKey(List<BoxGraphDTO.Node> nodes, String boxTitle) {
    if (nodes.isEmpty()) return null;
    String title = boxTitle == null ? "" : boxTitle.trim();
    if (!title.isEmpty()) {
      for (var n : nodes) {
        if ("event".equals(n.type()) && title.equals(Optional.ofNullable(n.name()).orElse("").trim())) {
          return n.key();
        }
      }
    }
    for (var n : nodes) {
      if ("event".equals(n.type())) return n.key();
    }
    for (var n : nodes) {
      if ("root".equals(n.type())) return n.key();
    }
    return nodes.get(0).key();
  }

  /**
   * 黄帝史略演示关系网（Excel 未导入关系页时对齐产品稿：家庭 / 师从 / 君臣 / 敌对）。
   */
  private BoxGraphDTO buildHuangDiDemonstrationGraph(String boxId) {
    String center = "hd_center_" + boxId;
    var nodes = new ArrayList<BoxGraphDTO.Node>();
    var edges = new ArrayList<BoxGraphDTO.Edge>();

    nodes.add(node(center, "event", "黄帝", "{\"group\":\"\"}"));
    nodes.add(node("hd_shaodian", "person", "少典", "{\"group\":\"家庭\"}"));
    nodes.add(node("hd_fubao", "person", "附宝", "{\"group\":\"家庭\"}"));
    nodes.add(node("hd_leizu", "person", "嫘祖", "{\"group\":\"家庭\"}"));
    nodes.add(node("hd_changyi", "person", "昌意", "{\"group\":\"家庭\"}"));
    nodes.add(node("hd_xuanxiao", "person", "玄嚣", "{\"group\":\"家庭\"}"));
    nodes.add(node("hd_qibo", "person", "岐伯", "{\"group\":\"师从\"}"));
    nodes.add(node("hd_guangcheng", "person", "广成子", "{\"group\":\"师从\"}"));
    nodes.add(node("hd_fenghou", "person", "风后", "{\"group\":\"君臣\"}"));
    nodes.add(node("hd_limu", "person", "力牧", "{\"group\":\"君臣\"}"));
    nodes.add(node("hd_changxian", "person", "常先", "{\"group\":\"君臣\"}"));
    nodes.add(node("hd_cangjie", "person", "仓颉", "{\"group\":\"君臣\"}"));
    nodes.add(node("hd_linglun", "person", "伶伦", "{\"group\":\"君臣\"}"));
    nodes.add(node("hd_yandi", "person", "炎帝", "{\"group\":\"敌对\"}"));
    nodes.add(node("hd_chiyou", "person", "蚩尤", "{\"group\":\"敌对\"}"));
    nodes.add(node("hd_hunyu", "person", "荤粥", "{\"group\":\"敌对\"}"));

    edges.add(edge(center, "hd_shaodian", "父亲"));
    edges.add(edge(center, "hd_fubao", "母亲"));
    edges.add(edge(center, "hd_leizu", "妻子"));
    edges.add(edge("hd_leizu", "hd_changyi", "儿子"));
    edges.add(edge("hd_leizu", "hd_xuanxiao", "儿子"));
    edges.add(edge(center, "hd_qibo", "问医"));
    edges.add(edge(center, "hd_guangcheng", "问道"));
    edges.add(edge(center, "hd_fenghou", "大臣"));
    edges.add(edge(center, "hd_limu", "大臣"));
    edges.add(edge(center, "hd_changxian", "大臣"));
    edges.add(edge(center, "hd_cangjie", "史官"));
    edges.add(edge(center, "hd_linglun", "乐官"));
    edges.add(edge(center, "hd_yandi", "阪泉之战"));
    edges.add(edge(center, "hd_chiyou", "涿鹿之战"));
    edges.add(edge(center, "hd_hunyu", "驱逐"));

    return new BoxGraphDTO(center, nodes, edges);
  }

  private static BoxGraphDTO.Node node(String key, String type, String name, String extraJson) {
    return new BoxGraphDTO.Node(key, type, name, null, null, null, extraJson);
  }

  private static BoxGraphDTO.Edge edge(String from, String to, String label) {
    return new BoxGraphDTO.Edge(from, to, label);
  }

  /**
   * Excel 未导入「关系」页时，用「历史单元（人物）— 本史略」补一条默认可视关系，避免线上关系 Tab 全空。
   */
  private BoxGraphDTO syntheticUnitEventGraph(String boxId) {
    try {
      Map<String, Object> row = jdbcTemplate.queryForMap(
          "SELECT b.title AS box_title, b.unit_id AS unit_id, u.name AS unit_name "
              + "FROM historical_box b JOIN historical_unit u ON u.id = b.unit_id AND u.status = 1 "
              + "WHERE b.id = ? AND b.status = 1",
          boxId
      );
      String unitName = Optional.ofNullable((String) row.get("unit_name")).orElse("历史单元").trim();
      String boxTitle = Optional.ofNullable((String) row.get("box_title")).orElse("史略").trim();
      if (unitName.isEmpty()) unitName = "历史单元";
      if (boxTitle.isEmpty()) boxTitle = "史略";

      String kUnit = "synthetic_unit_" + boxId;
      String kEvent = "synthetic_event_" + boxId;
      var nUnit = new BoxGraphDTO.Node(kUnit, "person", unitName, null, null, null, "{}");
      var nEvent = new BoxGraphDTO.Node(kEvent, "event", boxTitle, null, null, null, "{}");
      var e = new BoxGraphDTO.Edge(kUnit, kEvent, "本史略");
      return new BoxGraphDTO(kEvent, new ArrayList<>(List.of(nUnit, nEvent)), new ArrayList<>(List.of(e)));
    } catch (Exception ignored) {
      return null;
    }
  }

  public BoxCritiquesDTO loadCritiques(String boxId) {
    ensureDeepTab("critique", boxId);
    findBox(boxId);
    int max = props.getBox().getCritiques().getMaxCount();
    List<BoxCritiquesDTO.Item> items = jdbcTemplate.query(
        "SELECT title,blurb,author,era_text,year_value,content,source FROM box_critique WHERE box_id=? ORDER BY sort_order ASC, id ASC LIMIT ?",
        (rs, rowNum) -> new BoxCritiquesDTO.Item(
            rs.getString("title"),
            rs.getString("blurb"),
            rs.getString("author"),
            rs.getString("era_text"),
            (Integer) rs.getObject("year_value"),
            rs.getString("content"),
            rs.getString("source")
        ),
        boxId,
        max
    );
    return new BoxCritiquesDTO(items);
  }

  public BoxRelicsDTO loadRelics(String boxId) {
    ensureDeepTab("relic", boxId);
    findBox(boxId);
    int max = props.getBox().getRelics().getMaxCount();
    List<BoxRelicsDTO.Item> items = jdbcTemplate.query(
        "SELECT name,image_url,summary,description,museum,priority_code FROM box_relic WHERE box_id=? ORDER BY sort_order ASC, id ASC LIMIT ?",
        (rs, rowNum) -> new BoxRelicsDTO.Item(
            rs.getString("name"),
            rs.getString("image_url"),
            rs.getString("summary"),
            rs.getString("description"),
            rs.getString("museum"),
            rs.getString("priority_code")
        ),
        boxId,
        max
    );
    return new BoxRelicsDTO(items);
  }

  private Map<String, Object> findBox(String boxId) {
    Integer exists = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM historical_box WHERE id=? AND status=1",
        Integer.class,
        boxId
    );
    if (exists == null || exists == 0) {
      throw ApiException.notFound("box not found");
    }
    return jdbcTemplate.queryForMap(
        "SELECT id,unit_id,title,category_key,start_year,end_year,blurb,detail_md,detail_md_flash,detail_md_pro,original_ref_json "
            + "FROM historical_box WHERE id=? AND status=1",
        boxId
    );
  }

  /** 通过 Excel「史略 ID」等业务码解析盒子头信息（id 与 business_code 任一命中） */
  public BoxHeaderDTO loadHeaderByBusinessCode(String code) {
    String id = jdbcTemplate.query(
        "SELECT id FROM historical_box WHERE status=1 AND (business_code=? OR id=?) LIMIT 1",
        (rs, rowNum) -> rs.getString("id"),
        code,
        code
    ).stream().findFirst().orElseThrow(() -> ApiException.notFound("box not found"));
    return loadHeader(id);
  }

  private boolean exists(String sql, Object... args) {
    Integer v = jdbcTemplate.queryForObject(sql, Integer.class, args);
    return v != null && v > 0;
  }

  private static String yearLabel(int year) {
    return year < 0 ? ("前" + Math.abs(year)) : String.valueOf(year);
  }

  private static String categoryName(String key) {
    return switch (key) {
      case "junji" -> "君纪";
      case "shichen" -> "士臣";
      case "minlu" -> "民录";
      case "dianzhi" -> "典制";
      case "shilue" -> "事略";
      default -> key;
    };
  }

  private BoxHeaderDTO.Access buildAccess(String boxId) {
    BoxHeaderDTO.TabAccess graphUnlocked = new BoxHeaderDTO.TabAccess(false, null, null);
    var ctx = UserContextHolder.get();
    boolean authed = ctx.authenticated();
    if (!authed) {
      BoxHeaderDTO.TabAccess lockedLogin =
          new BoxHeaderDTO.TabAccess(true, "LOGIN_REQUIRED", new BoxHeaderDTO.UnlockAction("OPEN_LOGIN"));
      return new BoxHeaderDTO.Access(false, new BoxHeaderDTO.Tabs(graphUnlocked, lockedLogin, lockedLogin, lockedLogin));
    }
    long uid = ctx.userId();
    BoxHeaderDTO.TabAccess critique = deepTabReadService.tabAccess(uid, boxId, true, "critique");
    BoxHeaderDTO.TabAccess relic = deepTabReadService.tabAccess(uid, boxId, true, "relic");
    BoxHeaderDTO.TabAccess original = deepTabReadService.tabAccess(uid, boxId, true, "original");
    return new BoxHeaderDTO.Access(false, new BoxHeaderDTO.Tabs(graphUnlocked, critique, relic, original));
  }

  private void ensureTabAllowed(String tab, String boxId) {
    if (tab.equals("detail") || tab.equals("graph")) {
      return;
    }
    ensureDeepTab(tab, boxId);
  }

  private void ensureDeepTab(String tab, String boxId) {
    if (!tab.equals("critique") && !tab.equals("relic") && !tab.equals("original")) {
      return;
    }
    var ctx = UserContextHolder.get();
    if (!ctx.authenticated()) {
      throw ApiException.unauthorized("login required");
    }
    deepTabReadService.ensurePaidDeepTab(ctx.userId(), boxId, tab);
  }

  /**
   * 与 {@link #loadHeader} 的 hasOriginal 一致：占位符 "{}" / "[]" 视为未配置，避免前端只展示空 JSON。
   */
  private JsonNode parseOriginalRefJson(String raw) {
    if (raw == null || raw.isBlank()) return null;
    try {
      JsonNode node = objectMapper.readTree(raw);
      if (node == null || node.isNull() || node.isMissingNode()) return null;
      if ((node.isObject() || node.isArray()) && node.size() == 0) return null;
      return node;
    } catch (Exception ignored) {
      return null;
    }
  }
}
