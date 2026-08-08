package com.pandahis.histomap.user.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.api.ErrorCode;
import com.pandahis.histomap.user.interfaces.dto.FeedbackDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.FeedbackSubmitRequest;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
@SpringBootTest
@ActiveProfiles("test")
class FeedbackServiceTest {
  @Autowired JdbcTemplate jdbcTemplate;
  @Autowired ObjectMapper objectMapper;

  @TempDir Path tempDir;

  FeedbackImageStorageService imageStorageService;
  FeedbackService feedbackService;

  @BeforeEach
  void setUp() {
    imageStorageService = new FeedbackImageStorageService(tempDir.toString());
    feedbackService = new FeedbackService(jdbcTemplate, objectMapper, imageStorageService);
    jdbcTemplate.update("DELETE FROM user_feedback");
    ensureUser(1L);
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

  @Test
  void submitStoresFeedback() {
    FeedbackDetailDTO dto =
        feedbackService.submit(
            1L, new FeedbackSubmitRequest("feature", "首页加载有点慢，希望优化", List.of()));
    assertTrue(dto.id() > 0);
    assertEquals("feature", dto.feedbackType());
    assertEquals("首页加载有点慢，希望优化", dto.content());
    assertEquals("pending", dto.status());
  }

  @Test
  void rejectInvalidType() {
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                feedbackService.submit(
                    1L, new FeedbackSubmitRequest("unknown", "内容", List.of())));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }

  @Test
  void enforceDailyLimit() {
    for (int i = 0; i < 5; i++) {
      feedbackService.submit(1L, new FeedbackSubmitRequest("other", "第" + i + "条反馈内容", List.of()));
    }
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                feedbackService.submit(
                    1L, new FeedbackSubmitRequest("other", "第6条应被拦截", List.of())));
    assertEquals(ErrorCode.RATE_LIMITED, ex.getCode());
  }

  @Test
  void rejectExternalImageHost() {
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                feedbackService.normalizeImageUrls(
                    1L,
                    List.of(
                        "https://evil.com/api/v1/feedback/images/files/1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg")));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }

  @Test
  void rejectCrossUserFilename() throws Exception {
    String filename = "2_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg";
    Files.write(tempDir.resolve(filename), new byte[] {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0x00});
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                feedbackService.normalizeImageUrls(
                    1L, List.of("https://www.pandahis.com/api/v1/feedback/images/files/" + filename)));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }

  @Test
  void acceptOwnedExistingImageAsCanonicalPath() throws Exception {
    String filename = "1_cccccccccccccccccccccccccccccccc.jpg";
    // minimal jpeg header so looksLikeImage path not needed for existsOwned
    Files.write(tempDir.resolve(filename), new byte[] {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0x00});
    List<String> urls =
        feedbackService.normalizeImageUrls(
            1L,
            List.of("https://www.pandahis.com/api/v1/feedback/images/files/" + filename));
    assertEquals(List.of(FeedbackService.IMAGE_PATH_PREFIX + filename), urls);
  }

  @Test
  void extractFilenameRejectsNestedPath() {
    ApiException ex =
        assertThrows(
            ApiException.class,
            () ->
                FeedbackService.extractFeedbackFilename(
                    "https://evil.com/feedback/images/files/../1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg"));
    assertEquals(ErrorCode.INVALID_ARGUMENT, ex.getCode());
  }
}
