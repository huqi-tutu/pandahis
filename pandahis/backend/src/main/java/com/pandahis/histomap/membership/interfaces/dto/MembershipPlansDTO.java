package com.pandahis.histomap.membership.interfaces.dto;

import java.util.List;

public record MembershipPlansDTO(List<Plan> plans) {
  public record Plan(
      String id,
      String name,
      int priceCent,
      int durationDays,
      boolean isDefault,
      String tagText,
      List<String> benefits
  ) {}
}

