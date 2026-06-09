package com.pandahis.histomap.invite.interfaces.dto;

public record InviteMeDTO(
    String inviteCode,
    int readBalance,
    int invitedCount,
    int inviteRewardReads
) {}
