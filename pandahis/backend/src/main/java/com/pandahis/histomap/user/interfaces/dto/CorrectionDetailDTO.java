package com.pandahis.histomap.user.interfaces.dto;

public record CorrectionDetailDTO(
    long id,
    String boxId,
    String boxTitle,
    String unitId,
    String civilizationName,
    String dynastyName,
    String sourceType,
    String selectedText,
    String reason,
    String status,
    String createdAt
) {}
