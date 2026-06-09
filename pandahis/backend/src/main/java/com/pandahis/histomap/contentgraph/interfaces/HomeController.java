package com.pandahis.histomap.contentgraph.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.contentgraph.interfaces.dto.HomeGridDTO;
import com.pandahis.histomap.contentgraph.interfaces.dto.HomeMatrixDTO;
import com.pandahis.histomap.contentgraph.interfaces.service.HomeGridService;
import com.pandahis.histomap.contentgraph.interfaces.service.HomeMatrixService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class HomeController {
  private final HomeGridService homeGridService;
  private final HomeMatrixService homeMatrixService;

  public HomeController(HomeGridService homeGridService, HomeMatrixService homeMatrixService) {
    this.homeGridService = homeGridService;
    this.homeMatrixService = homeMatrixService;
  }

  @GetMapping("/home/grid")
  public ApiResponse<HomeGridDTO> grid() {
    return ApiResponse.ok(RequestIdHolder.get(), homeGridService.load());
  }

  @GetMapping("/home/matrix")
  public ApiResponse<HomeMatrixDTO> matrix(
      @RequestParam long civId,
      @RequestParam(required = false) String expanded
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), homeMatrixService.load(civId, parseExpanded(expanded)));
  }

  private static java.util.Set<String> parseExpanded(String expanded) {
    if (expanded == null || expanded.isBlank()) {
      return java.util.Set.of();
    }
    java.util.LinkedHashSet<String> out = new java.util.LinkedHashSet<>();
    for (String part : expanded.split(",")) {
      String k = part.trim();
      if (!k.isEmpty()) out.add(k);
    }
    return out;
  }
}

