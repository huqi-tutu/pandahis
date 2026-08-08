package com.pandahis.histomap.invite.interfaces.dto;

import java.util.List;

public record InviteMeDTO(
    String inviteCode,
    int readBalance,
    int invitedCount,
    int inviteRewardReads,
    List<InviteeDTO> invitees
) {}
