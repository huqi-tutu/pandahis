package com.pandahis.histomap;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles({"test", "dev"})
class V5AlignmentApiTest {

  private static final String AUTH = "Bearer dev-local-token";

  @Autowired
  private MockMvc mockMvc;

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
  void unitSwimMatrix_returnsFiveLanes() throws Exception {
    mockMvc.perform(get("/units/huaxia_song_shenzong/swim-matrix"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.lanes.length()").value(5))
        .andExpect(jsonPath("$.data.lanes[0].layout").exists())
        .andExpect(jsonPath("$.data.sheetWidthRpx").isNumber());
  }

  @Test
  void graphNodeDetail_returnsRelationFields() throws Exception {
    mockMvc.perform(get("/boxes/box_wutai_1079/graph/nodes/person_sushi"))
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
}
