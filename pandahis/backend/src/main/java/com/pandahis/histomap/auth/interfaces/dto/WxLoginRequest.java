package com.pandahis.histomap.auth.interfaces.dto;

import jakarta.validation.constraints.NotBlank;

public record WxLoginRequest(
    @NotBlank(message = "code required") String code,
    /** 可选：被邀请人首次注册时携带，用于给邀请人发放阅读数 */
    String inviteCode
) {
  public WxLoginRequest {
    inviteCode = inviteCode == null ? null : inviteCode.trim();
    if (inviteCode != null && inviteCode.isEmpty()) {
      inviteCode = null;
    }
  }
}
