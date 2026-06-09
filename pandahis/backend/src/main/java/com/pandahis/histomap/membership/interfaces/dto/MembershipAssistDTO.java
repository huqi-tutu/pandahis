package com.pandahis.histomap.membership.interfaces.dto;

import java.util.List;

public record MembershipAssistDTO(
    int targetCount,
    int currentCount,
    boolean completed,
    boolean rewardClaimed,
    String rewardPlanName,
    int rewardDurationDays,
    String membershipEndAt,
    String assistDeadlineAt,
    List<AssistParticipantDTO> participants
) {}
