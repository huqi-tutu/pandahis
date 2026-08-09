package com.pandahis.histomap.user.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.api.ErrorCode;
import com.pandahis.histomap.user.interfaces.dto.CorrectionDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.CorrectionSubmitRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class CorrectionServiceTest {
  @Autowired JdbcTemplate jdbcTemplate;
  @Autowired CorrectionService correctionService;

  @BeforeEach
  void setUp() {
    jdbcTemplate.update("DELETE FROM user_box_correction");
    jdbcTemplate.update("DELETE FROM box_critique");
    jdbcTemplate.update("DELETE FROM box_relic");
    jdbcTemplate.update("DELETE FROM historical_box WHERE id=?", "box_corr_test");
    ensureUser(1L);
    seedBox();
  }

  private void ensureUser(long userId) {
    Integer n =
        jdbcTemplate.queryForObject("SELECT COUNT(1) FROM app_user WHERE id=?", Integer.class, userId);
    if (n != null && n > 0) return;
    jdbcTemplate.update(
        "INSERT INTO app_user(id, nickname, avatar_url, phone_e164) VALUES (?,?,?,?)",
        userId,
        "tester",
        null,
        null);
  }

  private void seedBox() {
    jdbcTemplate.update(
        "INSERT INTO historical_box("
            + "id, emperor_id, regime_id, dynasty_id, civilization_code, civilization_name, "
            + "dynasty_name, title, category_key, start_year, end_year, status"
            + ") VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
        "box_corr_test",
        "emp_x",
        "reg_x",
        "dyn_x",
        "HX",
        "华夏",
        "北宋",
        "测试史略",
        "event",
        1000,
        1001);
  }

  private long seedCritique() {
    jdbcTemplate.update(
        "INSERT INTO box_critique("
            + "component_id, shilue_id, shilue_name, box_id, title, author, era_text, content, source, sort_order"
            + ") VALUES (?,?,?,?,?,?,?,?,?,1)",
        "box_corr_test_CRIT_001",
        "box_corr_test",
        "测试史略",
        "box_corr_test",
        "角度A",
        "作者",
        "北宋",
        "评述正文",
        "出处");
    return jdbcTemplate.queryForObject(
        "SELECT id FROM box_critique WHERE component_id=?",
        Long.class,
        "box_corr_test_CRIT_001");
  }

  private long seedRelic() {
    jdbcTemplate.update(
        "INSERT INTO box_relic("
            + "component_id, shilue_id, shilue_name, box_id, name, description, museum, sort_order"
            + ") VALUES (?,?,?,?,?,?,?,1)",
        "box_corr_test_RELIC_001",
        "box_corr_test",
        "测试史略",
        "box_corr_test",
        "见证物",
        "见证介绍",
        "博物馆");
    return jdbcTemplate.queryForObject(
        "SELECT id FROM box_relic WHERE component_id=?",
        Long.class,
        "box_corr_test_RELIC_001");
  }

  @Test
  void submitBoxDetailWithoutSourceRef() {
    CorrectionDetailDTO dto =
        correctionService.submit(
            1L,
            new CorrectionSubmitRequest(
                "box_corr_test", "box_detail_selection", "有误", "选中句", null));
    assertTrue(dto.id() > 0);
    assertEquals("box_detail_selection", dto.sourceType());
    assertNull(dto.sourceRefId());
    assertEquals("测试史略", dto.boxTitle());
  }

  @Test
  void submitCritiqueStoresSourceRefId() {
    long critiqueId = seedCritique();
    CorrectionDetailDTO dto =
        correctionService.submit(
            1L,
            new CorrectionSubmitRequest(
                "box_corr_test", "critique_detail_selection", "评述有误", "片段", critiqueId));
    assertEquals(critiqueId, dto.sourceRefId());
    assertEquals("critique_detail_selection", dto.sourceType());
  }

  @Test
  void submitRelicStoresSourceRefId() {
    long relicId = seedRelic();
    CorrectionDetailDTO dto =
        correctionService.submit(
            1L,
            new CorrectionSubmitRequest(
                "box_corr_test", "relic_detail_selection", null, "片段", relicId));
    assertEquals(relicId, dto.sourceRefId());
  }

  @Test
  void rejectCritiqueWithoutSourceRefId() {
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                correctionService.submit(
                    1L,
                    new CorrectionSubmitRequest(
                        "box_corr_test", "critique_detail_selection", "x", "y", null)));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }

  @Test
  void rejectMismatchedSourceRefId() {
    long relicId = seedRelic();
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                correctionService.submit(
                    1L,
                    new CorrectionSubmitRequest(
                        "box_corr_test", "critique_detail_selection", "x", "y", relicId)));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }
}
