package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record HomeMatrixStateDTO(
    String civilizationCode,
    String lastDynastyKey,
    List<String> collapsedDynastyKeys,
    Integer lastScrollTopPx,
    String updatedAt
) {}
