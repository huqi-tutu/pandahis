package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

/** 阅读足迹热力图：仅包含有阅读的日期，date 为 ISO 格式（yyyy-MM-dd） */
public record ReadingHeatmapDTO(String from, String to, List<Day> days) {
  public record Day(String date, int count) {}
}
