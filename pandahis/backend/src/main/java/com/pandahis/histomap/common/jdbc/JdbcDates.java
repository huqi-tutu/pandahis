package com.pandahis.histomap.common.jdbc;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.Date;

/** MySQL TIMESTAMP 经 JdbcTemplate 常为 LocalDateTime，统一转为 OffsetDateTime。 */
public final class JdbcDates {
  private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

  private JdbcDates() {}

  public static OffsetDateTime toOffsetDateTime(Object value) {
    if (value == null) {
      return null;
    }
    if (value instanceof OffsetDateTime odt) {
      return odt;
    }
    if (value instanceof LocalDateTime ldt) {
      return ldt.atZone(ZONE).toOffsetDateTime();
    }
    if (value instanceof java.sql.Timestamp ts) {
      return ts.toInstant().atZone(ZONE).toOffsetDateTime();
    }
    if (value instanceof Date d) {
      return d.toInstant().atZone(ZONE).toOffsetDateTime();
    }
    throw new IllegalArgumentException("unsupported temporal type: " + value.getClass().getName());
  }
}
