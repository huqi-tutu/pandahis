package com.pandahis.histomap.common.web;

import com.pandahis.histomap.common.api.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class HealthController {
  @GetMapping("/health")
  public ApiResponse<Map<String, Object>> health() {
    return ApiResponse.ok(RequestIdHolder.get(), Map.of("status", "ok"));
  }
}

