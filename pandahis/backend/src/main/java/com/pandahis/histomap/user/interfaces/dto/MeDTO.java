package com.pandahis.histomap.user.interfaces.dto;

public record MeDTO(
    String nickname,
    String avatarUrl,
    String phoneMasked,
    long favoriteCount,
    long footprintCount,
    long learnDaysCount,
    String membershipStatus,
    String membershipEndAt
) {}

