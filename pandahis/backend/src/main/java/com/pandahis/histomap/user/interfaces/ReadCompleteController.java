package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.ReadCompleteListDTO;
import com.pandahis.histomap.user.interfaces.service.ReadCompleteService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ReadCompleteController {
  private final ReadCompleteService readCompleteService;

  public ReadCompleteController(ReadCompleteService readCompleteService) {
    this.readCompleteService = readCompleteService;
  }

  @RequireAuth
  @PutMapping("/boxes/{boxId}/read-complete")
  public ApiResponse<Map<String, Object>> markComplete(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    readCompleteService.markComplete(UserContextHolder.get().userId(), boxId);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }

  @RequireAuth
  @DeleteMapping("/boxes/{boxId}/read-complete")
  public ApiResponse<Map<String, Object>> unmarkComplete(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    readCompleteService.unmarkComplete(UserContextHolder.get().userId(), boxId);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }

  @RequireAuth
  @GetMapping("/read-complete/boxes")
  public ApiResponse<ReadCompleteListDTO> list(
      @RequestParam(defaultValue = "1") @Min(1) int page,
      @RequestParam(defaultValue = "20") @Min(1) @Max(50) int pageSize
  ) {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        readCompleteService.list(UserContextHolder.get().userId(), page, pageSize)
    );
  }
}
