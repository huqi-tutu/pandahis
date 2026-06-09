package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.MeDTO;
import com.pandahis.histomap.user.interfaces.service.MeService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class MeController {
  private final MeService meService;

  public MeController(MeService meService) {
    this.meService = meService;
  }

  @RequireAuth
  @GetMapping("/me")
  public ApiResponse<MeDTO> me() {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), meService.load(userId));
  }

  @RequireAuth
  @PatchMapping("/me/profile")
  public ApiResponse<MeDTO> updateProfile(@Valid @RequestBody UpdateProfileRequest body) {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), meService.updateNickname(userId, body.nickname()));
  }

  public record UpdateProfileRequest(@NotBlank @Size(min = 1, max = 32) String nickname) {}
}

