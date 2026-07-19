package com.pandahis.histomap.user.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CorrectionSubmitRequest(
    @NotBlank @Size(max = 128) String boxId,
    @NotBlank @Size(max = 32) String sourceType,
    @Size(max = 500) String reason,
    @Size(max = 4000) String selectedText
) {}
