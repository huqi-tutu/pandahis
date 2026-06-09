package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.FavoriteListDTO;
import com.pandahis.histomap.user.interfaces.service.FavoriteService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping
public class FavoriteController {
  private final FavoriteService favoriteService;

  public FavoriteController(FavoriteService favoriteService) {
    this.favoriteService = favoriteService;
  }

  @RequireAuth
  @PostMapping("/favorites/boxes/{boxId}")
  public ApiResponse<Map<String, Object>> favorite(@PathVariable @NotBlank @Size(max = 128) String boxId) {
    favoriteService.favorite(UserContextHolder.get().userId(), boxId);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }

  @RequireAuth
  @DeleteMapping("/favorites/boxes/{boxId}")
  public ApiResponse<Map<String, Object>> unfavorite(@PathVariable @NotBlank @Size(max = 128) String boxId) {
    favoriteService.unfavorite(UserContextHolder.get().userId(), boxId);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }

  @RequireAuth
  @GetMapping("/favorites/boxes")
  public ApiResponse<FavoriteListDTO> list(
      @RequestParam(defaultValue = "1") @Min(1) int page,
      @RequestParam(defaultValue = "20") @Min(1) @Max(50) int pageSize
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), favoriteService.list(UserContextHolder.get().userId(), page, pageSize));
  }
}

