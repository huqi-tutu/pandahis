package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.FootprintListDTO;
import com.pandahis.histomap.user.interfaces.service.FootprintService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping
public class FootprintController {
  private final FootprintService footprintService;

  public FootprintController(FootprintService footprintService) {
    this.footprintService = footprintService;
  }

  @RequireAuth
  @PostMapping("/footprints/boxes/{boxId}/view")
  public ApiResponse<Map<String, Object>> view(@PathVariable @NotBlank @Size(max = 128) String boxId) {
    footprintService.view(UserContextHolder.get().userId(), boxId);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }

  @RequireAuth
  @GetMapping("/footprints/boxes")
  public ApiResponse<FootprintListDTO> list(
      @RequestParam(defaultValue = "1") @Min(1) int page,
      @RequestParam(defaultValue = "20") @Min(1) @Max(50) int pageSize
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), footprintService.list(UserContextHolder.get().userId(), page, pageSize));
  }
}

