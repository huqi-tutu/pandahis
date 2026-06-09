package com.pandahis.histomap.contentgraph.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.contentgraph.interfaces.dto.*;
import com.pandahis.histomap.contentgraph.interfaces.service.BoxService;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class BoxController {
  private final BoxService boxService;

  public BoxController(BoxService boxService) {
    this.boxService = boxService;
  }

  /** 史略业务码（如 HXWD0001）或等于主键 id 时解析头信息（需放在通配 `/boxes/{boxId}` 之前） */
  @GetMapping("/boxes/by-code/{businessCode}")
  public ApiResponse<BoxHeaderDTO> headerByCode(
      @PathVariable @NotBlank @Size(max = 64) String businessCode
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadHeaderByBusinessCode(businessCode));
  }

  @GetMapping("/boxes/{boxId}")
  public ApiResponse<BoxHeaderDTO> header(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadHeader(boxId));
  }

  @GetMapping("/boxes/{boxId}/detail")
  public ApiResponse<BoxDetailDTO> detail(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadDetail(boxId));
  }

  @GetMapping("/boxes/{boxId}/graph")
  public ApiResponse<BoxGraphDTO> graph(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadGraph(boxId));
  }

  @GetMapping("/boxes/{boxId}/critiques")
  public ApiResponse<BoxCritiquesDTO> critiques(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadCritiques(boxId));
  }

  @GetMapping("/boxes/{boxId}/relics")
  public ApiResponse<BoxRelicsDTO> relics(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadRelics(boxId));
  }

  @GetMapping("/boxes/{boxId}/graph/nodes/{nodeKey}")
  public ApiResponse<GraphNodeDetailDTO> graphNode(
      @PathVariable @NotBlank @Size(max = 128) String boxId,
      @PathVariable @NotBlank @Size(max = 64) String nodeKey
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadGraphNodeDetail(boxId, nodeKey));
  }

  @GetMapping("/boxes/{boxId}/original-ref")
  public ApiResponse<BoxOriginalRefDTO> originalRef(
      @PathVariable @NotBlank @Size(max = 128) String boxId
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), boxService.loadOriginalRef(boxId));
  }
}

