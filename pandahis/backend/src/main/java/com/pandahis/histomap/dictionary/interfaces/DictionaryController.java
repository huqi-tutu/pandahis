package com.pandahis.histomap.dictionary.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.dictionary.interfaces.dto.DictionaryLookupDTO;
import com.pandahis.histomap.dictionary.interfaces.service.DictionaryService;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DictionaryController {
  private final DictionaryService dictionaryService;

  public DictionaryController(DictionaryService dictionaryService) {
    this.dictionaryService = dictionaryService;
  }

  @GetMapping("/dictionary/lookup")
  public ApiResponse<DictionaryLookupDTO> lookup(
      @RequestParam("q") @NotBlank @Size(max = 32) String q
  ) {
    return ApiResponse.ok(RequestIdHolder.get(), dictionaryService.lookup(q));
  }
}
