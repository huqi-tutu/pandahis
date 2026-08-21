package com.pandahis.histomap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles({"test", "dev"})
class V5AlignmentApiTest {

  private static final String AUTH = "Bearer dev-local-token";

  @Autowired
  private MockMvc mockMvc;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @BeforeEach
  void cleanHomeMatrixState() {
    jdbcTemplate.update("DELETE FROM user_home_matrix_state WHERE user_id=1");
    jdbcTemplate.update("DELETE FROM user_box_reading_progress WHERE user_id=1");
    jdbcTemplate.update("DELETE FROM user_box_tab_read_ledger WHERE user_id=1");
    jdbcTemplate.update("UPDATE app_user SET read_balance=3 WHERE id=1");
  }

  @Test
  void anonymousOriginalRef_isPublicAndContainsData() throws Exception {
    mockMvc.perform(get("/boxes/GLBL_01079/original-ref"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.originalRef").isNotEmpty());
  }

  @Test
  void anonymousHeader_reportsOriginalUnlocked() throws Exception {
    mockMvc.perform(get("/boxes/GLBL_01079"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.access.tabs.original.locked").value(false));
  }

  @Test
  void anonymousFavoriteEndpoints_requireAuthentication() throws Exception {
    mockMvc.perform(post("/favorites/boxes/GLBL_01079"))
        .andExpect(status().isUnauthorized());
    mockMvc.perform(delete("/favorites/boxes/GLBL_01079"))
        .andExpect(status().isUnauthorized());
    mockMvc.perform(get("/favorites/boxes"))
        .andExpect(status().isUnauthorized());
    mockMvc.perform(post("/favorites/units/dyn_song_hx"))
        .andExpect(status().isUnauthorized());
    mockMvc.perform(delete("/favorites/units/dyn_song_hx"))
        .andExpect(status().isUnauthorized());
    mockMvc.perform(get("/favorites/units"))
        .andExpect(status().isUnauthorized());
  }

  @Test
  void authenticatedUnitFavorite_isSeparateFromBoxFavorite() throws Exception {
    mockMvc.perform(post("/favorites/units/dyn_song_hx")
            .header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk());

    mockMvc.perform(get("/favorites/units")
            .header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.total").value(1))
        .andExpect(jsonPath("$.data.items[0].unitId").value("dyn_song_hx"));

    mockMvc.perform(get("/me").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.favoriteCount").value(1));

    mockMvc.perform(post("/favorites/boxes/GLBL_01079")
            .header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk());

    mockMvc.perform(get("/me").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.favoriteCount").value(2));
  }

  @Test
  void authenticatedOriginalRef_doesNotConsumeReadBalanceOrCreateLedger() throws Exception {
    Integer balanceBefore = jdbcTemplate.queryForObject(
        "SELECT read_balance FROM app_user WHERE id=1", Integer.class);
    Integer ledgerBefore = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_tab_read_ledger WHERE user_id=1 AND box_id=? AND tab_key='original'",
        Integer.class,
        "GLBL_01079");

    mockMvc.perform(get("/boxes/GLBL_01079/original-ref")
            .header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.originalRef").isNotEmpty());

    assertEquals(balanceBefore, jdbcTemplate.queryForObject(
        "SELECT read_balance FROM app_user WHERE id=1", Integer.class));
    assertEquals(ledgerBefore, jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_tab_read_ledger WHERE user_id=1 AND box_id=? AND tab_key='original'",
        Integer.class,
        "GLBL_01079"));
  }

  @Test
  void homeGrid_returnsSparseCells() throws Exception {
    mockMvc.perform(get("/home/grid"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.timeAxis").isArray())
        .andExpect(jsonPath("$.data.civilizations").isArray())
        .andExpect(jsonPath("$.data.cells").isArray());
  }

  @Test
  void homeMatrix_returnsBlocksWithGeometry() throws Exception {
    mockMvc.perform(get("/home/matrix").param("civId", "1"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.rows").isArray())
        .andExpect(jsonPath("$.data.blocks[0].unitId").exists())
        .andExpect(jsonPath("$.data.blocks[0].leftPct").isNumber())
        .andExpect(jsonPath("$.data.blocks[0].widthPct").isNumber())
        .andExpect(jsonPath("$.data.totalHRpx").isNumber());
  }

  @Test
  void homeMatrix_collapsedDynasty_hasExpandableRow() throws Exception {
    mockMvc.perform(get("/home/matrix").param("civId", "1"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.rows[?(@.expandable == true)]").exists());
  }

  @Test
  void homeMatrix_blockHasSeamExtensionFields() throws Exception {
    mockMvc.perform(get("/home/matrix").param("civId", "1"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.blocks[0].fillSeamFix").exists())
        .andExpect(jsonPath("$.data.blocks[0].entryId").exists());
  }

  @Test
  void homeMatrix_expandedParam_showsMoreBlocks() throws Exception {
    mockMvc.perform(get("/home/matrix").param("civId", "1").param("expanded", "dyn_song_hx"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.rows[?(@.expanded == true)]").exists());
  }

  @Test
  void unitSwimMatrix_returnsElevenLanes() throws Exception {
    mockMvc.perform(get("/units/huaxia_song_shenzong/swim-matrix"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.lanes.length()").value(11))
        .andExpect(jsonPath("$.data.lanes[0].label").value("君王"))
        .andExpect(jsonPath("$.data.lanes[1].label").value("诸侯"))
        .andExpect(jsonPath("$.data.lanes[10].label").value("蕃祚"))
        .andExpect(jsonPath("$.data.lanes[0].layout").exists())
        .andExpect(jsonPath("$.data.lanes[0].key").exists())
        .andExpect(jsonPath("$.data.lanes[0].icon").exists())
        .andExpect(jsonPath("$.data.lanes[0].readProgressText").exists())
        .andExpect(jsonPath("$.data.lanes[0].priorityViews.p0").exists())
        .andExpect(jsonPath("$.data.lanes[0].trackHeightRpx").isNumber())
        .andExpect(jsonPath("$.data.sheetWidthRpx").isNumber());
  }

  @Test
  void graphNodeDetail_returnsRelationFields() throws Exception {
    mockMvc.perform(get("/boxes/GLBL_01079/graph/nodes/person_sushi"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.name").value("苏轼"))
        .andExpect(jsonPath("$.data.category").value("人物"))
        .andExpect(jsonPath("$.data.summary").isNotEmpty());
  }

  @Test
  void me_returnsLearnDaysCount() throws Exception {
    mockMvc.perform(get("/me").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.learnDaysCount").value(2))
        .andExpect(jsonPath("$.data.nickname").value("测试用户"));
  }

  @Test
  void homeMatrixState_defaultForFirstVisit() throws Exception {
    mockMvc.perform(get("/me/home-matrix-state").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.civilizationCode").value("HX"))
        .andExpect(jsonPath("$.data.collapsedDynastyKeys").isArray())
        .andExpect(jsonPath("$.data.collapsedDynastyKeys.length()").value(0));
  }

  @Test
  void homeMatrixState_upsertsAndReturnsUserState() throws Exception {
    mockMvc.perform(put("/me/home-matrix-state")
            .header(HttpHeaders.AUTHORIZATION, AUTH)
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
                {
                  "civilizationCode": "HX",
                  "lastDynastyKey": "唐",
                  "collapsedDynastyKeys": ["西汉", "唐"],
                  "lastScrollTopPx": 1280
                }
                """))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.lastDynastyKey").value("唐"))
        .andExpect(jsonPath("$.data.collapsedDynastyKeys[0]").value("西汉"))
        .andExpect(jsonPath("$.data.lastScrollTopPx").value(1280));

    mockMvc.perform(get("/me/home-matrix-state").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.lastDynastyKey").value("唐"))
        .andExpect(jsonPath("$.data.collapsedDynastyKeys.length()").value(2));
  }

  @Test
  void boxReadingProgress_defaultEmptyThenUpsertAndClearEdges() throws Exception {
    mockMvc.perform(get("/me/boxes/GLBL_01079/reading-progress").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.boxId").value("GLBL_01079"))
        .andExpect(jsonPath("$.data.progressPct").doesNotExist());

    mockMvc.perform(put("/me/boxes/GLBL_01079/reading-progress")
            .header(HttpHeaders.AUTHORIZATION, AUTH)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"progressPct\":42,\"scrollTopPx\":1280}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").value(42))
        .andExpect(jsonPath("$.data.scrollTopPx").value(1280));

    mockMvc.perform(get("/me/boxes/GLBL_01079/reading-progress").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").value(42))
        .andExpect(jsonPath("$.data.scrollTopPx").value(1280));

    // 过浅：清除
    mockMvc.perform(put("/me/boxes/GLBL_01079/reading-progress")
            .header(HttpHeaders.AUTHORIZATION, AUTH)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"progressPct\":3,\"scrollTopPx\":20}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").doesNotExist())
        .andExpect(jsonPath("$.data.scrollTopPx").doesNotExist());

    mockMvc.perform(get("/me/boxes/GLBL_01079/reading-progress").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").doesNotExist());
  }

  @Test
  void boxReadingProgress_originalNamespaceIndependentFromDetail() throws Exception {
    mockMvc.perform(put("/me/boxes/GLBL_01079/reading-progress")
            .header(HttpHeaders.AUTHORIZATION, AUTH)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"progressPct\":42,\"scrollTopPx\":1280}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").value(42));

    mockMvc.perform(put("/me/boxes/GLBL_01079__original/reading-progress")
            .header(HttpHeaders.AUTHORIZATION, AUTH)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"progressPct\":70,\"scrollTopPx\":880}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.boxId").value("GLBL_01079__original"))
        .andExpect(jsonPath("$.data.progressPct").value(70))
        .andExpect(jsonPath("$.data.scrollTopPx").value(880));

    mockMvc.perform(get("/me/boxes/GLBL_01079/reading-progress").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").value(42))
        .andExpect(jsonPath("$.data.scrollTopPx").value(1280));

    mockMvc.perform(get("/me/boxes/GLBL_01079__original/reading-progress").header(HttpHeaders.AUTHORIZATION, AUTH))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.progressPct").value(70))
        .andExpect(jsonPath("$.data.scrollTopPx").value(880));
  }
}
