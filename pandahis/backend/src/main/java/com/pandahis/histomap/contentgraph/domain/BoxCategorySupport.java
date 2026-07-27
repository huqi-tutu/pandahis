package com.pandahis.histomap.contentgraph.domain;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * 产品层史略分类与泳道配置。
 * <p>
 * 标注层 category_key 与泳道可不完全一致（见 {@link #swimLaneKey}）；
 * 朝代详情页固定 11 泳道，顺序与展示名以本类为准。
 */
public final class BoxCategorySupport {

  public record CategoryDef(String key, String label, String borderColor, String layout) {}

  /** 朝代详情页固定 11 泳道（顺序不可变；边框色 = 绢帛六色按序循环 c1→c6） */
  private static final List<CategoryDef> SWIM_LANES = List.of(
      new CategoryDef("junji", "君王", "#A2734F", "continuous"),
      new CategoryDef("zhuhou", "诸侯", "#63899C", "continuous"),
      new CategoryDef("zongqi", "宗戚", "#B99D5B", "continuous"),
      new CategoryDef("wenchen", "文臣", "#9A798F", "shichen"),
      new CategoryDef("wujiang", "武将", "#7D8A6A", "shichen"),
      new CategoryDef("shilue", "事略", "#A46A65", "continuous"),
      new CategoryDef("dianzhi", "典制", "#A2734F", "continuous"),
      new CategoryDef("lunzhu", "论著", "#63899C", "isolated"),
      new CategoryDef("huanguan", "宦官", "#B99D5B", "isolated"),
      new CategoryDef("shuzhong", "庶众", "#9A798F", "isolated"),
      new CategoryDef("fanzhu", "蕃祚", "#7D8A6A", "continuous")
  );

  /** historical_box.category_key → 泳道 key */
  private static final Map<String, String> SWIM_LANE_BY_BOX_CATEGORY = Map.ofEntries(
      Map.entry("junji", "junji"),
      Map.entry("zhuhou", "zhuhou"),
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
      "zhuhou",
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
      Map.entry("zhuhou", "诸侯"),
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

  /** 将库表 category_key 映射到 11 泳道之一；未知则丢弃 */
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

  /** 是否为人物类史略（君王/诸侯/宗戚/文臣/武将/宦官/庶众） */
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
