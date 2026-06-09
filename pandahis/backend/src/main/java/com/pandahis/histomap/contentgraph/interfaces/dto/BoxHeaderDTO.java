package com.pandahis.histomap.contentgraph.interfaces.dto;

public record BoxHeaderDTO(Box box, boolean isFavorite, TabSummary tabSummary, Access access) {
  public record Box(
      String id,
      String title,
      String subText,
      String blurb,
      String categoryKey,
      int startYear,
      int endYear
  ) {}

  public record TabSummary(boolean hasGraph, boolean hasCritiques, boolean hasRelics, boolean hasOriginal) {}

  public record Access(boolean boxLocked, Tabs tabs) {}

  public record Tabs(TabAccess graph, TabAccess critique, TabAccess relic, TabAccess original) {}

  public record TabAccess(boolean locked, String lockedReason, UnlockAction unlockAction) {}

  public record UnlockAction(String type) {}
}

