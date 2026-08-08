package com.pandahis.histomap.user.interfaces.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.user.interfaces.dto.FeedbackDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.FeedbackSubmitRequest;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class FeedbackService {
  private static final int MAX_CONTENT_LEN = 1000;
  private static final int MAX_IMAGES = 3;
  private static final int MAX_DAILY = 5;
  /** 入库仅存相对路径，杜绝外链主机伪造 */
  static final String IMAGE_PATH_PREFIX = "/feedback/images/files/";
  private static final Set<String> FEEDBACK_TYPES =
      Set.of("feature", "content", "partnership", "other");

  private final JdbcTemplate jdbcTemplate;
  private final ObjectMapper objectMapper;
  private final FeedbackImageStorageService imageStorageService;

  public FeedbackService(
      JdbcTemplate jdbcTemplate,
      ObjectMapper objectMapper,
      FeedbackImageStorageService imageStorageService
  ) {
    this.jdbcTemplate = jdbcTemplate;
    this.objectMapper = objectMapper;
    this.imageStorageService = imageStorageService;
  }

  @Transactional
  public FeedbackDetailDTO submit(long userId, FeedbackSubmitRequest req) {
    lockUserRow(userId);
    String type = normalizeType(req.feedbackType());
    if (!FEEDBACK_TYPES.contains(type)) {
      throw ApiException.invalidArgument("无效的反馈类型");
    }
    String content = normalizeContent(req.content());
    List<String> imageUrls = normalizeImageUrls(userId, req.imageUrls());
    enforceDailyLimit(userId);

    String imageJson = writeJson(imageUrls);
    KeyHolder keyHolder = new GeneratedKeyHolder();
    jdbcTemplate.update(
        con -> {
          var ps =
              con.prepareStatement(
                  "INSERT INTO user_feedback(user_id, feedback_type, content, image_urls_json, status) "
                      + "VALUES (?, ?, ?, ?, 'pending')",
                  new String[] {"id"});
          ps.setLong(1, userId);
          ps.setString(2, type);
          ps.setString(3, content);
          ps.setString(4, imageJson);
          return ps;
        },
        keyHolder);
    Number key = keyHolder.getKey();
    long id = key == null ? 0L : key.longValue();
    return requireOwnedDetail(userId, id);
  }

  public FeedbackDetailDTO detail(long userId, long feedbackId) {
    return requireOwnedDetail(userId, feedbackId);
  }

  private void lockUserRow(long userId) {
    try {
      Long id =
          jdbcTemplate.queryForObject(
              "SELECT id FROM app_user WHERE id=? FOR UPDATE", Long.class, userId);
      if (id == null) {
        throw ApiException.unauthorized("请先登录");
      }
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.unauthorized("请先登录");
    }
  }

  private void enforceDailyLimit(long userId) {
    Integer count =
        jdbcTemplate.queryForObject(
            "SELECT COUNT(1) FROM user_feedback "
                + "WHERE user_id=? AND created_at >= CURRENT_DATE "
                + "AND created_at < DATE_ADD(CURRENT_DATE, INTERVAL 1 DAY)",
            Integer.class,
            userId);
    if (count != null && count >= MAX_DAILY) {
      throw ApiException.rateLimited("今日反馈次数已达上限（" + MAX_DAILY + "次）");
    }
  }

  private FeedbackDetailDTO requireOwnedDetail(long userId, long feedbackId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT id, feedback_type, content, image_urls_json, status, created_at "
              + "FROM user_feedback WHERE id=? AND user_id=?",
          (rs, rowNum) ->
              new FeedbackDetailDTO(
                  rs.getLong("id"),
                  rs.getString("feedback_type"),
                  rs.getString("content"),
                  readJson(rs.getString("image_urls_json")),
                  rs.getString("status"),
                  formatTimestamp(rs.getObject("created_at", OffsetDateTime.class))),
          feedbackId,
          userId);
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.notFound("反馈不存在");
    }
  }

  private static String normalizeType(String raw) {
    return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
  }

  private static String normalizeContent(String raw) {
    String content = raw == null ? "" : raw.trim();
    if (content.isEmpty()) {
      throw ApiException.invalidArgument("请填写问题描述");
    }
    if (content.length() > MAX_CONTENT_LEN) {
      throw ApiException.invalidArgument("问题描述不能超过 " + MAX_CONTENT_LEN + " 字");
    }
    return content;
  }

  /**
   * 接受上传接口返回的绝对 URL 或相对路径，校验磁盘文件归属后，统一存相对路径。
   */
  List<String> normalizeImageUrls(long userId, List<String> raw) {
    if (raw == null || raw.isEmpty()) return List.of();
    if (raw.size() > MAX_IMAGES) {
      throw ApiException.invalidArgument("图片最多 " + MAX_IMAGES + " 张");
    }
    List<String> out = new ArrayList<>();
    for (String url : raw) {
      if (url == null || url.isBlank()) continue;
      String u = url.trim();
      if (u.length() > 512) {
        throw ApiException.invalidArgument("图片地址无效");
      }
      String filename = extractFeedbackFilename(u);
      if (!imageStorageService.existsOwned(userId, filename)) {
        throw ApiException.invalidArgument("图片地址无效或已过期");
      }
      out.add(IMAGE_PATH_PREFIX + filename);
    }
    if (out.size() > MAX_IMAGES) {
      throw ApiException.invalidArgument("图片最多 " + MAX_IMAGES + " 张");
    }
    return List.copyOf(out);
  }

  static String extractFeedbackFilename(String urlOrPath) {
    String u = urlOrPath.trim();
    int idx = u.lastIndexOf(IMAGE_PATH_PREFIX);
    if (idx < 0) {
      throw ApiException.invalidArgument("请先上传反馈图片");
    }
    // 拒绝把路径前缀嵌在 query / 伪造路径中间的情况：前缀后应为纯文件名
    String filename = u.substring(idx + IMAGE_PATH_PREFIX.length());
    int q = filename.indexOf('?');
    if (q >= 0) filename = filename.substring(0, q);
    int hash = filename.indexOf('#');
    if (hash >= 0) filename = filename.substring(0, hash);
    if (filename.contains("/") || filename.contains("\\")) {
      throw ApiException.invalidArgument("图片地址无效");
    }
    return FeedbackImageStorageService.sanitizeFilename(filename);
  }

  private String writeJson(List<String> urls) {
    try {
      return objectMapper.writeValueAsString(urls);
    } catch (JsonProcessingException e) {
      throw ApiException.internalError("反馈保存失败");
    }
  }

  private List<String> readJson(String json) {
    if (json == null || json.isBlank()) return List.of();
    try {
      List<String> list = objectMapper.readValue(json, new TypeReference<>() {});
      return list == null ? List.of() : List.copyOf(list);
    } catch (JsonProcessingException e) {
      return List.of();
    }
  }

  private static String formatTimestamp(OffsetDateTime at) {
    return at == null ? "" : at.toString();
  }
}
