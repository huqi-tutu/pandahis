package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.domain.BoxCategorySupport;
import com.pandahis.histomap.user.interfaces.dto.NoteDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteDynastyListDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteHighlightDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteListDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteSubmitRequest;
import com.pandahis.histomap.user.interfaces.dto.NoteUpdateRequest;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class NoteService {
  private static final int MAX_NOTES_PER_BOX = 200;
  private static final int MAX_TEXT = 2000;
  private static final String SOURCE_BOX_DETAIL = "box_detail_selection";
  private static final String SOURCE_CRITIQUE = "critique_detail_selection";
  private static final String SOURCE_RELIC = "relic_detail_selection";
  private static final String SOURCE_RELATION = "relation_graph_selection";
  private static final Set<String> SOURCE_TYPES =
      Set.of(SOURCE_BOX_DETAIL, SOURCE_CRITIQUE, SOURCE_RELIC, SOURCE_RELATION);

  private final JdbcTemplate jdbcTemplate;

  public NoteService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public NoteDetailDTO create(Long userId, NoteSubmitRequest req) {
    String sourceType = normalize(req.sourceType());
    if (!SOURCE_TYPES.contains(sourceType)) {
      throw ApiException.invalidArgument("invalid sourceType");
    }
    String selectedText = requireText(req.selectedText(), "selectedText");
    String noteText = normalizeOptional(req.noteText());
    if (noteText != null && noteText.length() > MAX_TEXT) {
      throw ApiException.invalidArgument("noteText too long");
    }

    BoxMeta meta = requireBoxMeta(req.boxId());
    Long sourceRefId = resolveSourceRefId(sourceType, meta.boxId(), req.sourceRefId());
    enforceNoteLimit(userId, meta.boxId());

    jdbcTemplate.update(
        "INSERT INTO user_box_note("
            + "user_id, box_id, box_title, box_category_key, unit_id, civilization_name, "
            + "dynasty_name, regime_name, emperor_name, coordinate_text, source_type, "
            + "source_ref_id, selected_text, note_text"
            + ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        userId,
        meta.boxId(),
        meta.boxTitle(),
        meta.categoryKey(),
        meta.unitId(),
        meta.civilizationName(),
        meta.dynastyName(),
        meta.regimeName(),
        meta.emperorName(),
        meta.coordinateText(),
        sourceType,
        sourceRefId,
        selectedText,
        noteText);

    Long id =
        jdbcTemplate.queryForObject(
            "SELECT id FROM user_box_note WHERE user_id=? AND box_id=? ORDER BY id DESC LIMIT 1",
            Long.class,
            userId,
            meta.boxId());
    return requireOwnedDetail(userId, id == null ? 0L : id);
  }

  public NoteDetailDTO update(Long userId, long noteId, NoteUpdateRequest req) {
    requireOwnedDetail(userId, noteId);
    String noteText = normalizeOptional(req.noteText());
    if (noteText != null && noteText.length() > MAX_TEXT) {
      throw ApiException.invalidArgument("noteText too long");
    }
    jdbcTemplate.update(
        "UPDATE user_box_note SET note_text=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
        noteText,
        noteId,
        userId);
    return requireOwnedDetail(userId, noteId);
  }

  public void delete(Long userId, long noteId) {
    requireOwnedDetail(userId, noteId);
    jdbcTemplate.update("DELETE FROM user_box_note WHERE id=? AND user_id=?", noteId, userId);
  }

  public NoteDetailDTO detail(Long userId, long noteId) {
    return requireOwnedDetail(userId, noteId);
  }

  public NoteDynastyListDTO listDynasties(Long userId) {
    List<DynastyAggRow> rows =
        jdbcTemplate.query(
            "SELECT n.unit_id, n.dynasty_name, n.civilization_name, d.start_year, c.sort_order AS civ_sort "
                + "FROM user_box_note n "
                + "LEFT JOIN historical_dynasty d ON d.id = n.unit_id "
                + "LEFT JOIN civilization_l1 c ON c.id = d.civilization_l1_id "
                + "WHERE n.user_id=?",
            (rs, rowNum) ->
                new DynastyAggRow(
                    trim(rs.getString("unit_id")),
                    trim(rs.getString("dynasty_name")),
                    trim(rs.getString("civilization_name")),
                    (Integer) rs.getObject("start_year"),
                    (Integer) rs.getObject("civ_sort")),
            userId);

    Map<String, NoteDynastyListDTO.Item> grouped = new LinkedHashMap<>();
    Map<String, SortKey> sortKeys = new LinkedHashMap<>();
    for (DynastyAggRow row : rows) {
      String dynastyId = row.unitId();
      String key = dynastyId.isEmpty() ? "name:" + row.dynastyName() + "|" + row.civilizationName() : dynastyId;
      NoteDynastyListDTO.Item existing = grouped.get(key);
      if (existing == null) {
        grouped.put(
            key,
            new NoteDynastyListDTO.Item(
                dynastyId,
                row.dynastyName(),
                row.civilizationName(),
                1,
                row.startYear()));
        sortKeys.put(key, new SortKey(row.startYear(), row.civSort(), row.dynastyName()));
      } else {
        grouped.put(
            key,
            new NoteDynastyListDTO.Item(
                existing.dynastyId(),
                existing.dynastyName(),
                existing.civilizationName(),
                existing.noteCount() + 1,
                existing.startYear()));
      }
    }

    List<NoteDynastyListDTO.Item> items =
        grouped.entrySet().stream()
            .sorted(Comparator.comparing(e -> sortKeys.get(e.getKey())))
            .map(Map.Entry::getValue)
            .toList();
    return new NoteDynastyListDTO(items);
  }

  public NoteListDTO listByDynasty(Long userId, String dynastyId, int page, int pageSize) {
    String unitId = normalize(dynastyId);
    if (unitId.isEmpty()) {
      throw ApiException.invalidArgument("dynastyId required");
    }
    Long total =
        jdbcTemplate.queryForObject(
            "SELECT COUNT(1) FROM user_box_note WHERE user_id=? AND unit_id=?",
            Long.class,
            userId,
            unitId);
    int offset = (page - 1) * pageSize;
    List<NoteListDTO.Item> items =
        jdbcTemplate.query(
            "SELECT id, box_id, box_title, selected_text, note_text, created_at "
                + "FROM user_box_note WHERE user_id=? AND unit_id=? "
                + "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (rs, rowNum) ->
                new NoteListDTO.Item(
                    rs.getLong("id"),
                    rs.getString("box_id"),
                    rs.getString("box_title"),
                    rs.getString("selected_text"),
                    rs.getString("note_text"),
                    formatTimestamp(rs.getObject("created_at", OffsetDateTime.class))),
            userId,
            unitId,
            pageSize,
            offset);
    return new NoteListDTO(page, pageSize, total == null ? 0 : total, items);
  }

  public List<NoteHighlightDTO> listHighlights(
      Long userId, String boxId, String sourceType, Long sourceRefId) {
    String normalizedBoxId = normalize(boxId);
    String normalizedSource = normalize(sourceType);
    if (normalizedBoxId.isEmpty() || !SOURCE_TYPES.contains(normalizedSource)) {
      throw ApiException.invalidArgument("invalid boxId or sourceType");
    }
    if (sourceRefId != null && sourceRefId > 0) {
      return jdbcTemplate.query(
          "SELECT id, selected_text FROM user_box_note "
              + "WHERE user_id=? AND box_id=? AND source_type=? AND source_ref_id=? "
              + "ORDER BY id ASC",
          (rs, rowNum) -> new NoteHighlightDTO(rs.getLong("id"), rs.getString("selected_text")),
          userId,
          normalizedBoxId,
          normalizedSource,
          sourceRefId);
    }
    return jdbcTemplate.query(
        "SELECT id, selected_text FROM user_box_note "
            + "WHERE user_id=? AND box_id=? AND source_type=? "
            + "ORDER BY id ASC",
        (rs, rowNum) -> new NoteHighlightDTO(rs.getLong("id"), rs.getString("selected_text")),
        userId,
        normalizedBoxId,
        normalizedSource);
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

  private void enforceNoteLimit(Long userId, String boxId) {
    Integer count =
        jdbcTemplate.queryForObject(
            "SELECT COUNT(1) FROM user_box_note WHERE user_id=? AND box_id=?",
            Integer.class,
            userId,
            boxId);
    if (count != null && count >= MAX_NOTES_PER_BOX) {
      throw ApiException.rateLimited("该史略笔记数量已达上限（" + MAX_NOTES_PER_BOX + "条）");
    }
  }

  private NoteDetailDTO requireOwnedDetail(Long userId, long noteId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT id, box_id, box_title, box_category_key, unit_id, civilization_name, dynasty_name, "
              + "regime_name, emperor_name, coordinate_text, source_type, source_ref_id, "
              + "selected_text, note_text, created_at, updated_at "
              + "FROM user_box_note WHERE id=? AND user_id=?",
          (rs, rowNum) ->
              new NoteDetailDTO(
                  rs.getLong("id"),
                  rs.getString("box_id"),
                  rs.getString("box_title"),
                  trim(rs.getString("box_category_key")),
                  BoxCategorySupport.displayName(trim(rs.getString("box_category_key"))),
                  rs.getString("unit_id"),
                  trim(rs.getString("civilization_name")),
                  trim(rs.getString("dynasty_name")),
                  trim(rs.getString("regime_name")),
                  trim(rs.getString("emperor_name")),
                  trim(rs.getString("coordinate_text")),
                  rs.getString("source_type"),
                  (Long) rs.getObject("source_ref_id"),
                  rs.getString("selected_text"),
                  rs.getString("note_text"),
                  formatTimestamp(rs.getObject("created_at", OffsetDateTime.class)),
                  formatTimestamp(rs.getObject("updated_at", OffsetDateTime.class))),
          noteId,
          userId);
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.notFound("note not found");
    }
  }

  private BoxMeta requireBoxMeta(String boxId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT id, title, dynasty_id, category_key, "
              + "COALESCE(NULLIF(TRIM(civilization_name), ''), '') AS civilization_name, "
              + "COALESCE(NULLIF(TRIM(dynasty_name), ''), '') AS dynasty_name, "
              + "COALESCE(NULLIF(TRIM(regime_name), ''), '') AS regime_name, "
              + "COALESCE(NULLIF(TRIM(emperor_name), ''), '') AS emperor_name "
              + "FROM historical_box WHERE id=?",
          (rs, rowNum) -> {
            String civ = trim(rs.getString("civilization_name"));
            String dynasty = trim(rs.getString("dynasty_name"));
            String regime = trim(rs.getString("regime_name"));
            String emperor = trim(rs.getString("emperor_name"));
            return new BoxMeta(
                rs.getString("id"),
                rs.getString("title"),
                trim(rs.getString("category_key")),
                rs.getString("dynasty_id"),
                civ,
                dynasty,
                regime,
                emperor,
                joinCoordinate(civ, dynasty, regime, emperor));
          },
          boxId);
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.notFound("box not found");
    }
  }

  static String joinCoordinate(String civ, String dynasty, String regime, String emperor) {
    List<String> parts = new ArrayList<>(4);
    appendCoordPart(parts, civ);
    appendCoordPart(parts, dynasty);
    appendCoordPart(parts, regime);
    appendCoordPart(parts, emperor);
    return String.join(" · ", parts);
  }

  private static void appendCoordPart(List<String> parts, String part) {
    if (part == null || part.isEmpty()) {
      return;
    }
    if (!parts.isEmpty() && parts.get(parts.size() - 1).equals(part)) {
      return;
    }
    parts.add(part);
  }

  private static String requireText(String value, String field) {
    String trimmed = normalizeOptional(value);
    if (trimmed == null) {
      throw ApiException.invalidArgument(field + " required");
    }
    if (trimmed.length() > MAX_TEXT) {
      throw ApiException.invalidArgument(field + " too long");
    }
    return trimmed;
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

  private static String trim(String value) {
    return value == null ? "" : value.trim();
  }

  private static String formatTimestamp(OffsetDateTime at) {
    return at == null ? null : at.toString();
  }

  private record BoxMeta(
      String boxId,
      String boxTitle,
      String categoryKey,
      String unitId,
      String civilizationName,
      String dynastyName,
      String regimeName,
      String emperorName,
      String coordinateText) {}

  private record DynastyAggRow(
      String unitId, String dynastyName, String civilizationName, Integer startYear, Integer civSort) {}

  private record SortKey(Integer startYear, Integer civSort, String dynastyName)
      implements Comparable<SortKey> {
    @Override
    public int compareTo(SortKey other) {
      int yearCmp = compareNullableInt(this.startYear, other.startYear);
      if (yearCmp != 0) {
        return yearCmp;
      }
      int civCmp = compareNullableInt(this.civSort, other.civSort);
      if (civCmp != 0) {
        return civCmp;
      }
      return String.valueOf(this.dynastyName).compareTo(String.valueOf(other.dynastyName));
    }

    private static int compareNullableInt(Integer a, Integer b) {
      if (a == null && b == null) {
        return 0;
      }
      if (a == null) {
        return 1;
      }
      if (b == null) {
        return -1;
      }
      return Integer.compare(a, b);
    }
  }
}
