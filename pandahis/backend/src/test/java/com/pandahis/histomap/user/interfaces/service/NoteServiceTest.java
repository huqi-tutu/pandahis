package com.pandahis.histomap.user.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.api.ErrorCode;
import com.pandahis.histomap.user.interfaces.dto.NoteDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteDynastyListDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteHighlightDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteListDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteSubmitRequest;
import com.pandahis.histomap.user.interfaces.dto.NoteUpdateRequest;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class NoteServiceTest {
  @Autowired JdbcTemplate jdbcTemplate;
  @Autowired NoteService noteService;

  @BeforeEach
  void setUp() {
    jdbcTemplate.update("DELETE FROM user_box_note");
    jdbcTemplate.update("DELETE FROM box_critique");
    jdbcTemplate.update("DELETE FROM box_relic");
    jdbcTemplate.update("DELETE FROM historical_box WHERE id LIKE 'box_note_%'");
    jdbcTemplate.update("DELETE FROM historical_dynasty WHERE id LIKE 'CD_NOTE_%'");
    jdbcTemplate.update("DELETE FROM civilization_l1 WHERE id IN (91, 92)");
    ensureUser(1L);
    seedCivAndDynasties();
  }

  private void ensureUser(long userId) {
    Integer n =
        jdbcTemplate.queryForObject("SELECT COUNT(1) FROM app_user WHERE id=?", Integer.class, userId);
    if (n != null && n > 0) {
      return;
    }
    jdbcTemplate.update(
        "INSERT INTO app_user(id, nickname, avatar_url, phone_e164) VALUES (?,?,?,?)",
        userId,
        "tester",
        null,
        null);
  }

  private void seedCivAndDynasties() {
    jdbcTemplate.update(
        "INSERT INTO civilization_l1(id, display_name, code, color_hex, sort_order, status)"
            + " VALUES (?,?,?,?,?,1)",
        91,
        "华夏",
        "HX",
        "#A2734F",
        1);
    jdbcTemplate.update(
        "INSERT INTO civilization_l1(id, display_name, code, color_hex, sort_order, status)"
            + " VALUES (?,?,?,?,?,1)",
        92,
        "西欧",
        "XO",
        "#63899C",
        11);
    jdbcTemplate.update(
        "INSERT INTO historical_dynasty("
            + "id, civilization_l1_id, civilization_name, civilization_code, name,"
            + " start_year, end_year, sort_order, status) VALUES (?,?,?,?,?,?,?,?,1)",
        "CD_NOTE_SANGUO",
        91,
        "华夏",
        "HX",
        "三国",
        220,
        280,
        1);
    jdbcTemplate.update(
        "INSERT INTO historical_dynasty("
            + "id, civilization_l1_id, civilization_name, civilization_code, name,"
            + " start_year, end_year, sort_order, status) VALUES (?,?,?,?,?,?,?,?,1)",
        "CD_NOTE_TANG",
        91,
        "华夏",
        "HX",
        "唐",
        618,
        907,
        2);
    jdbcTemplate.update(
        "INSERT INTO historical_dynasty("
            + "id, civilization_l1_id, civilization_name, civilization_code, name,"
            + " start_year, end_year, sort_order, status) VALUES (?,?,?,?,?,?,?,?,1)",
        "CD_NOTE_ROME",
        92,
        "西欧",
        "XO",
        "罗马",
        -27,
        476,
        3);
    jdbcTemplate.update(
        "INSERT INTO historical_dynasty("
            + "id, civilization_l1_id, civilization_name, civilization_code, name,"
            + " start_year, end_year, sort_order, status) VALUES (?,?,?,?,?,?,?,?,1)",
        "CD_NOTE_HX100",
        91,
        "华夏",
        "HX",
        "同年华夏",
        100,
        120,
        4);
    jdbcTemplate.update(
        "INSERT INTO historical_dynasty("
            + "id, civilization_l1_id, civilization_name, civilization_code, name,"
            + " start_year, end_year, sort_order, status) VALUES (?,?,?,?,?,?,?,?,1)",
        "CD_NOTE_XO100",
        92,
        "西欧",
        "XO",
        "同年西欧",
        100,
        130,
        5);
  }

  private void seedBox(
      String boxId,
      String dynastyId,
      String civ,
      String dynasty,
      String regime,
      String emperor,
      String title,
      String categoryKey) {
    jdbcTemplate.update(
        "INSERT INTO historical_box("
            + "id, emperor_id, regime_id, dynasty_id, civilization_code, civilization_name, "
            + "dynasty_name, regime_name, emperor_name, title, category_key, start_year, end_year, status"
            + ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
        boxId,
        "emp_note",
        "reg_note",
        dynastyId,
        "HX",
        civ,
        dynasty,
        regime,
        emperor,
        title,
        categoryKey,
        220,
        221);
  }

  private long seedCritique(String boxId) {
    jdbcTemplate.update(
        "INSERT INTO box_critique("
            + "component_id, shilue_id, shilue_name, box_id, title, author, era_text, content, source, sort_order"
            + ") VALUES (?,?,?,?,?,?,?,?,?,1)",
        boxId + "_CRIT_001",
        boxId,
        "测试史略",
        boxId,
        "角度A",
        "作者",
        "三国",
        "评述正文",
        "出处");
    return jdbcTemplate.queryForObject(
        "SELECT id FROM box_critique WHERE component_id=?", Long.class, boxId + "_CRIT_001");
  }

  @Test
  void createHighlightOnlyNoteStoresBoxMeta() {
    seedBox("box_note_a", "CD_NOTE_SANGUO", "华夏", "三国", "魏", "曹操", "孟德事略", "junji");
    NoteDetailDTO dto =
        noteService.create(
            1L,
            new NoteSubmitRequest(
                "box_note_a", "box_detail_selection", "选中的一句原文", null, null));
    assertTrue(dto.id() > 0);
    assertEquals("孟德事略", dto.boxTitle());
    assertEquals("junji", dto.boxCategoryKey());
    assertEquals("君王", dto.boxCategoryName());
    assertEquals("华夏", dto.civilizationName());
    assertEquals("三国", dto.dynastyName());
    assertEquals("魏", dto.regimeName());
    assertEquals("曹操", dto.emperorName());
    assertEquals("华夏 · 三国 · 魏 · 曹操", dto.coordinateText());
    assertEquals("选中的一句原文", dto.selectedText());
    assertNull(dto.noteText());
    assertEquals("CD_NOTE_SANGUO", dto.unitId());
  }

  @Test
  void createNoteWithRemark() {
    seedBox("box_note_b", "CD_NOTE_TANG", "华夏", "唐", "唐", "太宗", "贞观史略", "shilue");
    NoteDetailDTO dto =
        noteService.create(
            1L,
            new NoteSubmitRequest(
                "box_note_b", "box_detail_selection", "原文", "我的备注", null));
    assertEquals("我的备注", dto.noteText());
    assertEquals("事略", dto.boxCategoryName());
  }

  @Test
  void rejectSelectedTextOver2000() {
    seedBox("box_note_c", "CD_NOTE_TANG", "华夏", "唐", "唐", "太宗", "贞观史略", "shilue");
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                noteService.create(
                    1L,
                    new NoteSubmitRequest(
                        "box_note_c",
                        "box_detail_selection",
                        "x".repeat(2001),
                        null,
                        null)));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }

  @Test
  void rejectCritiqueWithoutSourceRefId() {
    seedBox("box_note_d", "CD_NOTE_SANGUO", "华夏", "三国", "蜀", "刘备", "先主", "junji");
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                noteService.create(
                    1L,
                    new NoteSubmitRequest(
                        "box_note_d", "critique_detail_selection", "片段", "笔记", null)));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }

  @Test
  void createCritiqueNoteStoresSourceRef() {
    seedBox("box_note_e", "CD_NOTE_SANGUO", "华夏", "三国", "蜀", "刘备", "先主", "junji");
    long critiqueId = seedCritique("box_note_e");
    NoteDetailDTO dto =
        noteService.create(
            1L,
            new NoteSubmitRequest(
                "box_note_e", "critique_detail_selection", "评述句", "评述笔记", critiqueId));
    assertEquals(critiqueId, dto.sourceRefId());
    assertEquals("critique_detail_selection", dto.sourceType());
  }

  @Test
  void weiShuNotesGroupUnderSanguo() {
    seedBox("box_note_wei", "CD_NOTE_SANGUO", "华夏", "三国", "魏", "曹操", "魏武", "junji");
    seedBox("box_note_shu", "CD_NOTE_SANGUO", "华夏", "三国", "蜀", "刘备", "先主", "junji");
    noteService.create(
        1L, new NoteSubmitRequest("box_note_wei", "box_detail_selection", "魏句", null, null));
    noteService.create(
        1L, new NoteSubmitRequest("box_note_shu", "box_detail_selection", "蜀句", "备注", null));
    List<NoteDynastyListDTO.Item> items = noteService.listDynasties(1L).items();
    NoteDynastyListDTO.Item sanguo =
        items.stream().filter(it -> "三国".equals(it.dynastyName())).findFirst().orElseThrow();
    assertEquals("CD_NOTE_SANGUO", sanguo.dynastyId());
    assertEquals(2, sanguo.noteCount());
    assertEquals("华夏", sanguo.civilizationName());
  }

  @Test
  void dynastiesSortedByStartYearThenCivilizationOrder() {
    seedBox("box_note_rome", "CD_NOTE_ROME", "西欧", "罗马", "罗马", "奥古斯都", "罗马史", "shilue");
    seedBox("box_note_tang", "CD_NOTE_TANG", "华夏", "唐", "唐", "太宗", "唐史", "shilue");
    seedBox("box_note_hx100", "CD_NOTE_HX100", "华夏", "同年华夏", "", "", "华夏同年", "shilue");
    seedBox("box_note_xo100", "CD_NOTE_XO100", "西欧", "同年西欧", "", "", "西欧同年", "shilue");
    noteService.create(
        1L, new NoteSubmitRequest("box_note_tang", "box_detail_selection", "唐句", null, null));
    noteService.create(
        1L, new NoteSubmitRequest("box_note_rome", "box_detail_selection", "罗马句", null, null));
    noteService.create(
        1L, new NoteSubmitRequest("box_note_xo100", "box_detail_selection", "西同年", null, null));
    noteService.create(
        1L, new NoteSubmitRequest("box_note_hx100", "box_detail_selection", "华同年", null, null));
    List<String> names =
        noteService.listDynasties(1L).items().stream().map(NoteDynastyListDTO.Item::dynastyName).toList();
    assertEquals(List.of("罗马", "同年华夏", "同年西欧", "唐"), names);
  }

  @Test
  void listNotesInDynastyNewestFirst() throws InterruptedException {
    seedBox("box_note_f", "CD_NOTE_TANG", "华夏", "唐", "唐", "太宗", "贞观", "shilue");
    NoteDetailDTO older =
        noteService.create(
            1L, new NoteSubmitRequest("box_note_f", "box_detail_selection", "旧句", "旧笔记", null));
    Thread.sleep(20);
    NoteDetailDTO newer =
        noteService.create(
            1L, new NoteSubmitRequest("box_note_f", "box_detail_selection", "新句", null, null));
    NoteListDTO list = noteService.listByDynasty(1L, "CD_NOTE_TANG", 1, 20);
    assertEquals(2, list.total());
    assertEquals(newer.id(), list.items().get(0).id());
    assertEquals(older.id(), list.items().get(1).id());
    assertEquals("新句", list.items().get(0).selectedText());
    assertNull(list.items().get(0).noteText());
  }

  @Test
  void updateAndDeleteNote() {
    seedBox("box_note_g", "CD_NOTE_TANG", "华夏", "唐", "唐", "太宗", "贞观", "shilue");
    NoteDetailDTO created =
        noteService.create(
            1L, new NoteSubmitRequest("box_note_g", "box_detail_selection", "原文", null, null));
    NoteDetailDTO updated = noteService.update(1L, created.id(), new NoteUpdateRequest("补写备注"));
    assertEquals("补写备注", updated.noteText());
    noteService.delete(1L, created.id());
    ApiException ex =
        assertThrows(ApiException.class, () -> noteService.detail(1L, created.id()));
    assertEquals(ErrorCode.NOT_FOUND, ex.getCode());
  }

  @Test
  void highlightsByBoxAndSource() {
    seedBox("box_note_h", "CD_NOTE_TANG", "华夏", "唐", "唐", "太宗", "贞观", "shilue");
    noteService.create(
        1L, new NoteSubmitRequest("box_note_h", "box_detail_selection", "详情句", "a", null));
    noteService.create(
        1L,
        new NoteSubmitRequest("box_note_h", "relation_graph_selection", "李世民", null, null));
    List<NoteHighlightDTO> detailMarks =
        noteService.listHighlights(1L, "box_note_h", "box_detail_selection", null);
    assertEquals(1, detailMarks.size());
    assertEquals("详情句", detailMarks.get(0).selectedText());
    List<NoteHighlightDTO> relationMarks =
        noteService.listHighlights(1L, "box_note_h", "relation_graph_selection", null);
    assertEquals(1, relationMarks.size());
    assertEquals("李世民", relationMarks.get(0).selectedText());
  }
}
