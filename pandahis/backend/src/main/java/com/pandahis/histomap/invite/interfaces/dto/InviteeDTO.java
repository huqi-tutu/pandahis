package com.pandahis.histomap.invite.interfaces.dto;

/** 我邀请成功的好友（注册即建立关系）。 */
public record InviteeDTO(
    String nickname, String avatarUrl, String registeredAt, int rewardReads) {}
