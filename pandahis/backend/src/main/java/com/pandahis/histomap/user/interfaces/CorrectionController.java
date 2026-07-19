package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.CorrectionDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.CorrectionListDTO;
import com.pandahis.histomap.user.interfaces.dto.CorrectionSubmitRequest;
import com.pandahis.histomap.user.interfaces.service.CorrectionService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CorrectionController {
  private final CorrectionService correctionService;

  public CorrectionController(CorrectionService correctionService) {
    this.correctionService = correctionService;
  }

  @RequireAuth
  @PostMapping("/corrections")
  public ApiResponse<CorrectionDetailDTO> submit(@Valid @RequestBody CorrectionSubmitRequest req) {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        correctionService.submit(UserContextHolder.get().userId(), req)
    );
  }

  @RequireAuth
  @GetMapping("/corrections")
  public ApiResponse<CorrectionListDTO> list(
      @RequestParam(defaultValue = "1") @Min(1) int page,
      @RequestParam(defaultValue = "20") @Min(1) @Max(50) int pageSize
  ) {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        correctionService.list(UserContextHolder.get().userId(), page, pageSize)
    );
  }

  @RequireAuth
  @GetMapping("/corrections/{id}")
  public ApiResponse<CorrectionDetailDTO> detail(@PathVariable long id) {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        correctionService.detail(UserContextHolder.get().userId(), id)
    );
  }
}
