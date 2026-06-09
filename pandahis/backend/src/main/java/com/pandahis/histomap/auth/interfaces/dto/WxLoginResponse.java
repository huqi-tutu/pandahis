package com.pandahis.histomap.auth.interfaces.dto;

public record WxLoginResponse(
    String accessToken,
    int expiresIn,
    /** 本次登录是否为新注册用户 */
    boolean newUser,
    /** 新用户且邀请码有效时，是否已写入邀请关系并发放奖励 */
    boolean inviteRecorded
) {}
