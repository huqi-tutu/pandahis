package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.BoxReadingProgressDTO;
import com.pandahis.histomap.user.interfaces.service.BoxReadingProgressService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class BoxReadingProgressController {
  private final BoxReadingProgressService boxReadingProgressService;

  public BoxReadingProgressController(BoxReadingProgressService boxReadingProgressService) {
    this.boxReadingProgressService = boxReadingProgressService;
  }

  @RequireAuth
  @GetMapping("/me/boxes/{boxId}/reading-progress")
  public ApiResponse<BoxReadingProgressDTO> load(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), boxReadingProgressService.load(userId, boxId));
  }

  @RequireAuth
  @PutMapping("/me/boxes/{boxId}/reading-progress")
  public ApiResponse<BoxReadingProgressDTO> save(
      @PathVariable @NotBlank @Size(max = 128) String boxId,
      @Valid @RequestBody SaveBoxReadingProgressRequest body
  ) {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(
        RequestIdHolder.get(),
        boxReadingProgressService.save(userId, boxId, body.progressPct(), body.scrollTopPx())
    );
  }

  public record SaveBoxReadingProgressRequest(
      @NotNull @Min(0) @Max(100) Integer progressPct,
      @PositiveOrZero Integer scrollTopPx
  ) {}
}
