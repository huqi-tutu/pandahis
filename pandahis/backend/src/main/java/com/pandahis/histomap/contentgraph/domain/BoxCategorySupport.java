package com.pandahis.histomap.contentgraph.domain;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * 产品层史略分类与泳道配置。
 * <p>
 * 标注层 category_key 与泳道可不完全一致（见 {@link #swimLaneKey}）；
 * 朝代详情页固定 10 泳道，顺序与展示名以本类为准。
 */
public final class BoxCategorySupport {

  public record CategoryDef(String key, String label, String borderColor, String layout) {}

  /** 朝代详情页固定 10 泳道（顺序不可变） */
  private static final List<CategoryDef> SWIM_LANES = List.of(
      new CategoryDef("junji", "君王", "#F1A805", "continuous"),
      new CategoryDef("zongqi", "宗戚", "#D4A5A5", "continuous"),
      new CategoryDef("wenchen", "文臣", "#E0C088", "shichen"),
      new CategoryDef("wujiang", "武将", "#C4A882", "shichen"),
      new CategoryDef("shilue", "事略", "#B3D9E0", "continuous"),
      new CategoryDef("dianzhi", "典制", "#92ADA4", "continuous"),
      new CategoryDef("lunzhu", "论著", "#A894B8", "isolated"),
      new CategoryDef("huanguan", "宦官", "#B8A9C9", "isolated"),
      new CategoryDef("shuzhong", "庶众", "#EDD5C0", "isolated"),
      new CategoryDef("fanzhu", "蕃祚", "#92ADA4", "continuous")
  );

  /** historical_box.category_key → 泳道 key */
  private static final Map<String, String> SWIM_LANE_BY_BOX_CATEGORY = Map.ofEntries(
      Map.entry("junji", "junji"),
      Map.entry("zongqi", "zongqi"),
      Map.entry("wenchen", "wenchen"),
      Map.entry("wujiang", "wujiang"),
      Map.entry("shilue", "shilue"),
      Map.entry("dianzhi", "dianzhi"),
      Map.entry("lunzhu", "lunzhu"),
      Map.entry("huanguan", "huanguan"),
      Map.entry("shuzhong", "shuzhong"),
      Map.entry("fanzhu", "fanzhu"),
      Map.entry("shichen", "wenchen"),
      Map.entry("minlu", "shuzhong")
  );

  /** 人物六类 + 历史别名；关系 Tab 仅对这些类型开放 */
  private static final Set<String> PERSON_CATEGORY_KEYS = Set.of(
      "junji",
      "zongqi",
      "wenchen",
      "wujiang",
      "huanguan",
      "shuzhong",
      "shichen",
      "minlu"
  );

  private static final Map<String, String> DISPLAY_NAMES = Map.ofEntries(
      Map.entry("junji", "君王"),
      Map.entry("zongqi", "宗戚"),
      Map.entry("wenchen", "文臣"),
      Map.entry("wujiang", "武将"),
      Map.entry("shilue", "事略"),
      Map.entry("dianzhi", "典制"),
      Map.entry("lunzhu", "论著"),
      Map.entry("huanguan", "宦官"),
      Map.entry("shuzhong", "庶众"),
      Map.entry("fanzhu", "蕃祚"),
      Map.entry("shichen", "士臣"),
      Map.entry("minlu", "民录")
  );

  private BoxCategorySupport() {}

  public static List<CategoryDef> swimLanes() {
    return SWIM_LANES;
  }

  /** 将库表 category_key 映射到 10 泳道之一；未知则丢弃 */
  public static Optional<String> swimLaneKey(String boxCategoryKey) {
    if (boxCategoryKey == null || boxCategoryKey.isBlank()) {
      return Optional.empty();
    }
    String lane = SWIM_LANE_BY_BOX_CATEGORY.get(boxCategoryKey.trim());
    return lane == null ? Optional.empty() : Optional.of(lane);
  }

  public static String displayName(String key) {
    if (key == null || key.isBlank()) {
      return "";
    }
    return DISPLAY_NAMES.getOrDefault(key, key);
  }

  /** 是否为人物类史略（君王/宗戚/文臣/武将/宦官/庶众） */
  public static boolean isPersonCategory(String boxCategoryKey) {
    if (boxCategoryKey == null || boxCategoryKey.isBlank()) {
      return false;
    }
    return PERSON_CATEGORY_KEYS.contains(boxCategoryKey.trim());
  }

  public static Optional<CategoryDef> swimLaneDef(String laneKey) {
    return SWIM_LANES.stream().filter(d -> d.key().equals(laneKey)).findFirst();
  }

  public static String laneBorderColor(String laneKey) {
    return swimLaneDef(laneKey).map(CategoryDef::borderColor).orElse("#84572F");
  }
}
