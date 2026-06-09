package com.pandahis.histomap.contentgraph.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitCivTabsDTO;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitHeroDTO;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitMatrixDTO;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import com.pandahis.histomap.contentgraph.interfaces.service.UnitService;
import com.pandahis.histomap.contentgraph.interfaces.service.UnitSwimMatrixService;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class UnitController {
  private final UnitService unitService;
  private final UnitSwimMatrixService unitSwimMatrixService;

  public UnitController(UnitService unitService, UnitSwimMatrixService unitSwimMatrixService) {
    this.unitService = unitService;
    this.unitSwimMatrixService = unitSwimMatrixService;
  }

  @GetMapping("/units/{unitId}")
  public ApiResponse<UnitHeroDTO> hero(
      @PathVariable @NotBlank @Size(max = 64) String unitId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), unitService.loadHero(unitId));
  }

  @GetMapping("/units/{unitId}/matrix")
  public ApiResponse<UnitMatrixDTO> matrix(
      @PathVariable @NotBlank @Size(max = 64) String unitId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), unitService.loadMatrix(unitId));
  }

  @GetMapping("/units/{unitId}/civ-tabs")
  public ApiResponse<UnitCivTabsDTO> civTabs(
      @PathVariable @NotBlank @Size(max = 64) String unitId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), unitService.loadCivTabs(unitId));
  }

  @GetMapping("/units/{unitId}/swim-matrix")
  public ApiResponse<UnitSwimMatrixDTO> swimMatrix(
      @PathVariable @NotBlank @Size(max = 64) String unitId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), unitSwimMatrixService.load(unitId));
  }
}

