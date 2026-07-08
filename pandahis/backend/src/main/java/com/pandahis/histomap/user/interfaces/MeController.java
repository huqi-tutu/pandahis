package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.HomeMatrixStateDTO;
import com.pandahis.histomap.user.interfaces.dto.MeDTO;
import com.pandahis.histomap.user.interfaces.service.HomeMatrixStateService;
import com.pandahis.histomap.user.interfaces.service.HomeMatrixStateService.SaveHomeMatrixStateCommand;
import com.pandahis.histomap.user.interfaces.service.MeService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class MeController {
  private final MeService meService;
  private final HomeMatrixStateService homeMatrixStateService;

  public MeController(MeService meService, HomeMatrixStateService homeMatrixStateService) {
    this.meService = meService;
    this.homeMatrixStateService = homeMatrixStateService;
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

  @RequireAuth
  @GetMapping("/me/home-matrix-state")
  public ApiResponse<HomeMatrixStateDTO> homeMatrixState() {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), homeMatrixStateService.load(userId));
  }

  @RequireAuth
  @PutMapping("/me/home-matrix-state")
  public ApiResponse<HomeMatrixStateDTO> saveHomeMatrixState(
      @Valid @RequestBody SaveHomeMatrixStateRequest body
  ) {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(
        RequestIdHolder.get(),
        homeMatrixStateService.save(
            userId,
            new SaveHomeMatrixStateCommand(
                body.civilizationCode(),
                body.lastDynastyKey(),
                body.collapsedDynastyKeys(),
                body.lastScrollTopPx()
            )
        )
    );
  }

  public record UpdateProfileRequest(@NotBlank @Size(min = 1, max = 32) String nickname) {}

  public record SaveHomeMatrixStateRequest(
      @Size(max = 16) String civilizationCode,
      @Size(max = 64) String lastDynastyKey,
      List<@Size(max = 64) String> collapsedDynastyKeys,
      @PositiveOrZero Integer lastScrollTopPx
  ) {}
}

