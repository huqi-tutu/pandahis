package com.pandahis.histomap.narration.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.narration.interfaces.dto.NarrationSynthesizeDTO;
import com.pandahis.histomap.narration.service.EdgeNarrationService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Base64;

@RestController
@RequestMapping("/narration")
public class NarrationController {
  private final EdgeNarrationService edgeNarrationService;

  public NarrationController(EdgeNarrationService edgeNarrationService) {
    this.edgeNarrationService = edgeNarrationService;
  }

  /** 将短文本合成为 MP3（Base64），无需微信同声传译插件。 */
  @PostMapping("/synthesize")
  public ApiResponse<NarrationSynthesizeDTO.Response> synthesize(
      @Valid @RequestBody NarrationSynthesizeDTO.Request body
  ) {
    byte[] mp3 = edgeNarrationService.synthesizeMp3(body.text());
    String b64 = Base64.getEncoder().encodeToString(mp3);
    return ApiResponse.ok(
        RequestIdHolder.get(), new NarrationSynthesizeDTO.Response(b64, "audio/mpeg"));
  }
}
