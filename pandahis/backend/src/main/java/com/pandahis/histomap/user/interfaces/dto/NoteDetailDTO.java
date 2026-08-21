package com.pandahis.histomap.user.interfaces.dto;

public record NoteDetailDTO(
    long id,
    String boxId,
    String boxTitle,
    String boxCategoryKey,
    String boxCategoryName,
    String unitId,
    String civilizationName,
    String dynastyName,
    String regimeName,
    String emperorName,
    String coordinateText,
    String sourceType,
    Long sourceRefId,
    String selectedText,
    String noteText,
    String createdAt,
    String updatedAt
) {}
