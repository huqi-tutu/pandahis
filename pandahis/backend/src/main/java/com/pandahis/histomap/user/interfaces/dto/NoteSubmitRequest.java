package com.pandahis.histomap.user.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record NoteSubmitRequest(
    @NotBlank @Size(max = 128) String boxId,
    @NotBlank @Size(max = 32) String sourceType,
    @NotBlank @Size(max = 2000) String selectedText,
    @Size(max = 2000) String noteText,
    Long sourceRefId
) {}
