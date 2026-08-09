package com.pandahis.histomap.common.feature;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class ConfigController {
  private final FeatureFlagService featureFlagService;

  public ConfigController(FeatureFlagService featureFlagService) {
    this.featureFlagService = featureFlagService;
  }

  @GetMapping("/config/features")
  public ApiResponse<FeatureFlagsDTO> features() {
    return ApiResponse.ok(RequestIdHolder.get(), loadFlags());
  }

  FeatureFlagsDTO loadFlags() {
    return new FeatureFlagsDTO(featureFlagService.isCivSwitchEnabled());
  }
}
