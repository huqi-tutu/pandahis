package com.pandahis.histomap.contentgraph.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.auth.UserContext;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.config.HistomapProperties;
import com.pandahis.histomap.user.interfaces.service.ReadCompleteService;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class BoxServiceOriginalAccessTest {
  @AfterEach
  void clearContext() {
    UserContextHolder.clear();
  }

  @Test
  void anonymousHeaderAlwaysReportsOriginalUnlocked() {
    UserContextHolder.set(UserContext.anonymous());
    JdbcTemplate jdbc = mock(JdbcTemplate.class);
    when(jdbc.queryForObject(anyString(), any(Class.class), any())).thenReturn(1);
    when(jdbc.queryForMap(anyString(), any())).thenReturn(Map.of(
        "id", "box-1", "title", "测试", "category_key", "person",
        "start_year", 1, "end_year", 2, "original_ref_json", "{\"originalText\":\"原文\"}",
        "entry_source", "extract", "civilization_name", "华夏", "dynasty_name", "夏"
    ));
    BoxService service = new BoxService(jdbc, new HistomapProperties(), new ObjectMapper(), mock(ReadCompleteService.class));

    assertFalse(service.loadHeader("box-1").access().tabs().original().locked());
  }

  @Test
  void anonymousCanLoadOriginalWithoutChargingDeepTab() {
    UserContextHolder.set(UserContext.anonymous());
    JdbcTemplate jdbc = mock(JdbcTemplate.class);
    when(jdbc.queryForObject(anyString(), any(Class.class), any())).thenReturn(1);
    when(jdbc.queryForMap(anyString(), any())).thenReturn(Map.of(
        "id", "box-1", "title", "测试", "category_key", "person",
        "start_year", 1, "end_year", 2, "original_ref_json", "{\"primarySource\":\"史记\",\"originalText\":\"原文\"}",
        "entry_source", "extract", "civilization_name", "华夏", "dynasty_name", "夏"
    ));
    BoxService service = new BoxService(jdbc, new HistomapProperties(), new ObjectMapper(), mock(ReadCompleteService.class));

    assertNotNull(service.loadOriginalRef("box-1").originalRef());
  }
}
