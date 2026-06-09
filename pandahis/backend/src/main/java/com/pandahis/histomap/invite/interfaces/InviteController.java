package com.pandahis.histomap.invite.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.invite.interfaces.dto.InviteMeDTO;
import com.pandahis.histomap.invite.service.InviteService;
import com.pandahis.histomap.invite.interfaces.dto.InviteBindDTO;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class InviteController {
  private final InviteService inviteService;

  public InviteController(InviteService inviteService) {
    this.inviteService = inviteService;
  }

  @RequireAuth
  @GetMapping("/invite/me")
  public ApiResponse<InviteMeDTO> me() {
    long userId = UserContextHolder.get().userId();
    String code = inviteService.ensureInviteCode(userId);
    int balance = inviteService.readBalance(userId);
    int invited = inviteService.countSuccessfulInvites(userId);
    return ApiResponse.ok(
        RequestIdHolder.get(),
        new InviteMeDTO(code, balance, invited, InviteService.INVITE_REWARD_READS)
    );
  }

  @RequireAuth
  @PostMapping("/invite/bind")
  public ApiResponse<InviteBindDTO> bind(@Valid @RequestBody InviteBindRequest body) {
    long userId = UserContextHolder.get().userId();
    var result = inviteService.bindInviteCode(userId, body.inviteCode());
    return ApiResponse.ok(RequestIdHolder.get(), new InviteBindDTO(result.bound(), result.message()));
  }

  public record InviteBindRequest(@NotBlank @Size(min = 4, max = 32) String inviteCode) {}
}
