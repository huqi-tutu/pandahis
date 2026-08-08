package com.pandahis.histomap.user.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;

public record FeedbackSubmitRequest(
    @NotBlank @Size(max = 32) String feedbackType,
    @NotBlank @Size(max = 1000) String content,
    @Size(max = 3) List<@Size(max = 512) String> imageUrls
) {}
