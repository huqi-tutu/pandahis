package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.user.interfaces.dto.CorrectionDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.CorrectionListDTO;
import com.pandahis.histomap.user.interfaces.dto.CorrectionSubmitRequest;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Set;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class CorrectionService {
  private static final int MAX_SUBMISSIONS_PER_BOX = 20;
  private static final String SOURCE_DYNASTY = "dynasty_canvas";
  private static final String SOURCE_BOX_DETAIL = "box_detail_selection";
  private static final String SOURCE_BOX_ORIGINAL = "box_original_selection";
  private static final String SOURCE_CRITIQUE = "critique_detail_selection";
  private static final String SOURCE_RELIC = "relic_detail_selection";
  private static final String SOURCE_RELATION = "relation_graph_selection";
  private static final Set<String> SOURCE_TYPES = Set.of(
      SOURCE_DYNASTY,
      SOURCE_BOX_DETAIL,
      SOURCE_BOX_ORIGINAL,
      SOURCE_CRITIQUE,
      SOURCE_RELIC,
      SOURCE_RELATION);

  private final JdbcTemplate jdbcTemplate;

  public CorrectionService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public CorrectionDetailDTO submit(Long userId, CorrectionSubmitRequest req) {
    String sourceType = normalize(req.sourceType());
    if (!SOURCE_TYPES.contains(sourceType)) {
      throw ApiException.invalidArgument("invalid sourceType");
    }
    String reason = normalizeOptional(req.reason());
    if (reason != null && reason.length() > 500) {
      throw ApiException.invalidArgument("reason too long");
    }
    String selectedText = normalizeOptional(req.selectedText());
    if (selectedText != null && selectedText.length() > 4000) {
      throw ApiException.invalidArgument("selectedText too long");
    }

    BoxMeta meta = requireBoxMeta(req.boxId());
    Long sourceRefId = resolveSourceRefId(sourceType, meta.boxId(), req.sourceRefId());
    enforceSubmissionLimit(userId, meta.boxId());

    jdbcTemplate.update(
        "INSERT INTO user_box_correction("
            + "user_id, box_id, box_title, unit_id, civilization_name, dynasty_name, "
            + "source_type, source_ref_id, selected_text, reason, status"
            + ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
        userId,
        meta.boxId(),
        meta.boxTitle(),
        meta.unitId(),
        meta.civilizationName(),
        meta.dynastyName(),
        sourceType,
        sourceRefId,
        selectedText,
        reason
    );

    Long id = jdbcTemplate.queryForObject(
        "SELECT id FROM user_box_correction WHERE user_id=? AND box_id=? ORDER BY id DESC LIMIT 1",
        Long.class,
        userId,
        meta.boxId()
    );
    return requireOwnedDetail(userId, id == null ? 0L : id);
  }

  public CorrectionListDTO list(Long userId, int page, int pageSize) {
    long total = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_correction WHERE user_id=?",
        Long.class,
        userId
    );
    int offset = (page - 1) * pageSize;
    List<CorrectionListDTO.Item> items = jdbcTemplate.query(
        "SELECT id, box_id, box_title, status, created_at "
            + "FROM user_box_correction WHERE user_id=? "
            + "ORDER BY created_at DESC, id DESC "
            + "LIMIT ? OFFSET ?",
        (rs, rowNum) -> new CorrectionListDTO.Item(
            rs.getLong("id"),
            rs.getString("box_id"),
            rs.getString("box_title"),
            rs.getString("status"),
            formatTimestamp(rs.getObject("created_at", OffsetDateTime.class))
        ),
        userId,
        pageSize,
        offset
    );
    return new CorrectionListDTO(page, pageSize, total, items);
  }

  public CorrectionDetailDTO detail(Long userId, long correctionId) {
    return requireOwnedDetail(userId, correctionId);
  }

  private Long resolveSourceRefId(String sourceType, String boxId, Long sourceRefId) {
    if (SOURCE_CRITIQUE.equals(sourceType)) {
      if (sourceRefId == null || sourceRefId <= 0) {
        throw ApiException.invalidArgument("sourceRefId required for critique");
      }
      requireOwnedSourceRef("SELECT COUNT(1) FROM box_critique WHERE id=? AND box_id=?", sourceRefId, boxId);
      return sourceRefId;
    }
    if (SOURCE_RELIC.equals(sourceType)) {
      if (sourceRefId == null || sourceRefId <= 0) {
        throw ApiException.invalidArgument("sourceRefId required for relic");
      }
      requireOwnedSourceRef("SELECT COUNT(1) FROM box_relic WHERE id=? AND box_id=?", sourceRefId, boxId);
      return sourceRefId;
    }
    return null;
  }

  private void requireOwnedSourceRef(String sql, long sourceRefId, String boxId) {
    Integer count = jdbcTemplate.queryForObject(sql, Integer.class, sourceRefId, boxId);
    if (count == null || count == 0) {
      throw ApiException.invalidArgument("invalid sourceRefId");
    }
  }

  private void enforceSubmissionLimit(Long userId, String boxId) {
    Integer count = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_correction WHERE user_id=? AND box_id=?",
        Integer.class,
        userId,
        boxId
    );
    if (count != null && count >= MAX_SUBMISSIONS_PER_BOX) {
      throw ApiException.rateLimited("该史略纠错次数已达上限（20次）");
    }
  }

  private CorrectionDetailDTO requireOwnedDetail(Long userId, long correctionId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT id, box_id, box_title, unit_id, civilization_name, dynasty_name, "
              + "source_type, source_ref_id, selected_text, reason, status, created_at "
              + "FROM user_box_correction WHERE id=? AND user_id=?",
          (rs, rowNum) -> new CorrectionDetailDTO(
              rs.getLong("id"),
              rs.getString("box_id"),
              rs.getString("box_title"),
              rs.getString("unit_id"),
              rs.getString("civilization_name"),
              rs.getString("dynasty_name"),
              rs.getString("source_type"),
              (Long) rs.getObject("source_ref_id"),
              rs.getString("selected_text"),
              rs.getString("reason"),
              rs.getString("status"),
              formatTimestamp(rs.getObject("created_at", OffsetDateTime.class))
          ),
          correctionId,
          userId
      );
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.notFound("correction not found");
    }
  }

  private BoxMeta requireBoxMeta(String boxId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT id, title, dynasty_id, "
              + "COALESCE(NULLIF(TRIM(civilization_name), ''), '') AS civilization_name, "
              + "COALESCE(NULLIF(TRIM(dynasty_name), ''), '') AS dynasty_name "
              + "FROM historical_box WHERE id=?",
          (rs, rowNum) -> new BoxMeta(
              rs.getString("id"),
              rs.getString("title"),
              rs.getString("dynasty_id"),
              rs.getString("civilization_name"),
              rs.getString("dynasty_name")
          ),
          boxId
      );
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.notFound("box not found");
    }
  }

  private static String normalize(String value) {
    return value == null ? "" : value.trim();
  }

  private static String normalizeOptional(String value) {
    if (value == null) {
      return null;
    }
    String trimmed = value.trim();
    return trimmed.isEmpty() ? null : trimmed;
  }

  private static String formatTimestamp(OffsetDateTime at) {
    return at == null ? null : at.toString();
  }

  private record BoxMeta(
      String boxId,
      String boxTitle,
      String unitId,
      String civilizationName,
      String dynastyName
  ) {}
}
