package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record FeedbackDetailDTO(
    long id,
    String feedbackType,
    String content,
    List<String> imageUrls,
    String status,
    String createdAt
) {}
