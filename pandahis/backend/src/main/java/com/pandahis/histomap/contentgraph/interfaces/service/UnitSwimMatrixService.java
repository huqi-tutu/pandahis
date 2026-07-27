package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.auth.UserContext;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.util.HistoryYearFormat;
import com.pandahis.histomap.contentgraph.domain.BoxCategorySupport;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import com.pandahis.histomap.user.interfaces.service.ReadCompleteService;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class UnitSwimMatrixService {
  private static final Logger log = LoggerFactory.getLogger(UnitSwimMatrixService.class);

  private final JdbcTemplate jdbcTemplate;
  private final UnitDynastyResolver dynastyResolver;
  private final ReadCompleteService readCompleteService;

  public UnitSwimMatrixService(
      JdbcTemplate jdbcTemplate,
      UnitDynastyResolver dynastyResolver,
      ReadCompleteService readCompleteService
  ) {
    this.jdbcTemplate = jdbcTemplate;
    this.dynastyResolver = dynastyResolver;
    this.readCompleteService = readCompleteService;
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
        "SELECT id, title, category_key, start_year, end_year, priority_code, priority_reason, importance_level, "
            + "peak_year, peak_reason, person_tag, blurb, entry_source "
            + "FROM historical_box WHERE dynasty_id=? AND status=1 "
            + "ORDER BY start_year ASC, id ASC",
        dynastyId
    );
    boxes = BoxEntryDeduper.hideThinExtractWhenSupplementExists(boxes);

    List<LaneSeed> laneSeeds = buildLaneSeeds(boxes, startYear, endYear);
    List<Integer> anchorYears = collectAnchorYears(laneSeeds);

    var ctx = UserContextHolder.get();
    Set<String> completedBoxIds = loadCompletedBoxIds(ctx, dynastyId);

    SwimTimeScale.Plan timePlan = SwimTimeScale.plan(startYear, endYear, anchorYears, laneSeeds.size());
    int recommendedSheetWidthRpx = refineSheetWidth(laneSeeds, timePlan);
    SwimTimeScale.Plan finalPlan = timePlan.scale().fitToViewport(
        anchorYears,
        recommendedSheetWidthRpx,
        timePlan.timeScaleMode()
    );
    int sheetWidthRpx = finalPlan.sheetWidthRpx();

    List<UnitSwimMatrixDTO.Lane> lanes = laneSeeds.stream()
        .map(seed -> buildLane(seed.def(), seed.bars(), finalPlan.scale(), sheetWidthRpx, completedBoxIds))
        .toList();

    SwimCanvasLayout.CanvasPlan canvas = SwimCanvasLayout.build(lanes);

    List<String> concurrent = loadConcurrentItems(civName, dynastyName, startYear, endYear);

    return new UnitSwimMatrixDTO(
        startYear,
        endYear,
        HistoryYearFormat.label(endYear),
        finalPlan.ticks(),
        finalPlan.gridLines(),
        finalPlan.timeSegments(),
        finalPlan.timeScaleMode(),
        canvas.lanes(),
        concurrent,
        sheetWidthRpx,
        canvas.canvasHeightRpx(),
        canvas.canvasPadLeftRpx(),
        canvas.categoryBands()
    );
  }

  private List<LaneSeed> buildLaneSeeds(List<Map<String, Object>> boxes, int startYear, int endYear) {
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
        String peakReason = b.get("peak_reason") == null ? null : String.valueOf(b.get("peak_reason")).trim();
        if (peakReason != null && peakReason.isEmpty()) {
          peakReason = null;
        }
        String priorityReason = b.get("priority_reason") == null ? null : String.valueOf(b.get("priority_reason")).trim();
        if (priorityReason != null && priorityReason.isEmpty()) {
          priorityReason = null;
        }
        bars.add(new SwimLaneLayout.SwimBarInput(
            (String) b.get("id"),
            (String) b.get("title"),
            bs,
            be,
            priority(b.get("priority_code"), b.get("importance_level")),
            peakYear,
            peakReason,
            "junji".equals(def.key()) || "zhuhou".equals(def.key()),
            personTag(b.get("person_tag")),
            priorityReason,
            entrySource(b.get("entry_source"))
        ));
      }
      laneSeeds.add(new LaneSeed(def, bars));
    }
    return laneSeeds;
  }

  private static List<Integer> collectAnchorYears(List<LaneSeed> laneSeeds) {
    List<Integer> anchors = new ArrayList<>();
    for (LaneSeed seed : laneSeeds) {
      for (SwimLaneLayout.SwimBarInput bar : seed.bars()) {
        int anchor = bar.anchorAtStart() || bar.peakYear() == null ? bar.start() : bar.peakYear();
        anchors.add(anchor);
      }
    }
    return anchors;
  }

  private UnitSwimMatrixDTO.Lane buildLane(
      BoxCategorySupport.CategoryDef def,
      List<SwimLaneLayout.SwimBarInput> bars,
      SwimTimeScale scale,
      int sheetWidthRpx,
      Set<String> completedBoxIds
  ) {
    Map<String, UnitSwimMatrixDTO.LaneView> views =
        SwimLaneLayout.buildPriorityViews(bars, scale, sheetWidthRpx, def.key(), def.label());
    UnitSwimMatrixDTO.LaneView defaultView = views.get("p3");
    int totalCount = bars.size();
    int readCount = (int) bars.stream().filter(bar -> completedBoxIds.contains(bar.boxId())).count();

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

  private int refineSheetWidth(List<LaneSeed> laneSeeds, SwimTimeScale.Plan timePlan) {
    int width = timePlan.sheetWidthRpx();
    for (int pass = 0; pass < 2; pass++) {
      int maxRows = 1;
      for (LaneSeed seed : laneSeeds) {
        UnitSwimMatrixDTO.LaneView view = SwimLaneLayout
            .buildPriorityViews(seed.bars(), timePlan.scale(), width, seed.def().key(), seed.def().label())
            .get("p3");
        maxRows = Math.max(maxRows, view.rowCount());
      }
      double factor = Math.max(1.0, Math.min(1.8, maxRows / 6.0));
      width = (int) Math.round(width * factor);
    }
    return Math.max(SwimTimeScale.MIN_SHEET_RPX, Math.min(SwimTimeScale.MAX_SHEET_RPX, width));
  }

  private static String laneIcon(String key) {
    return switch (key) {
      case "junji" -> "王";
      case "zhuhou" -> "侯";
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


  private static String personTag(Object raw) {
    if (raw == null) {
      return null;
    }
    String value = String.valueOf(raw).trim();
    return value.isEmpty() ? null : value;
  }

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

  private static String entrySource(Object raw) {
    if (raw == null) {
      return "extract";
    }
    String value = String.valueOf(raw).trim().toLowerCase();
    return "supplement".equals(value) ? "supplement" : "extract";
  }

  private Set<String> loadCompletedBoxIds(UserContext ctx, String dynastyId) {
    if (!ctx.authenticated()) {
      return Set.of();
    }
    try {
      return readCompleteService.completedBoxIdsForDynasty(ctx.userId(), dynastyId);
    } catch (Exception e) {
      log.warn("completedBoxIdsForDynasty failed userId={} dynastyId={}", ctx.userId(), dynastyId, e);
      return Set.of();
    }
  }

  private record LaneSeed(BoxCategorySupport.CategoryDef def, List<SwimLaneLayout.SwimBarInput> bars) {}
}
