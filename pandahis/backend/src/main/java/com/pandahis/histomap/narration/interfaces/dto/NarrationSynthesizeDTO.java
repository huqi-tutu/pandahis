package com.pandahis.histomap.narration.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class NarrationSynthesizeDTO {
  public record Request(@NotBlank @Size(max = 2000) String text) {}

  public record Response(String audioBase64, String mimeType) {}
}
