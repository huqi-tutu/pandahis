package com.pandahis.histomap.auth.interfaces;

import com.pandahis.histomap.auth.interfaces.dto.WxLoginRequest;
import com.pandahis.histomap.auth.interfaces.dto.WxLoginResponse;
import com.pandahis.histomap.auth.service.WxAuthService;
import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
public class AuthController {
  private final WxAuthService wxAuthService;

  public AuthController(WxAuthService wxAuthService) {
    this.wxAuthService = wxAuthService;
  }

  @PostMapping("/wx-login")
  public ApiResponse<WxLoginResponse> wxLogin(@Valid @RequestBody WxLoginRequest body) {
    WxLoginResponse out = wxAuthService.loginWithWxCode(body.code().trim(), body.inviteCode());
    return ApiResponse.ok(RequestIdHolder.get(), out);
  }
}
