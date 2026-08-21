package com.pandahis.histomap.user.interfaces.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record BoxReadingProgressDTO(
    String boxId,
    Integer progressPct,
    Integer scrollTopPx,
    String updatedAt
) {}
