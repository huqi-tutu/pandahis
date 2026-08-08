package com.pandahis.histomap.wikipedia.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.wikipedia.WikipediaLookupService;
import com.pandahis.histomap.wikipedia.WikipediaRateLimiter;
import com.pandahis.histomap.wikipedia.interfaces.dto.WikipediaLookupDTO;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
public class WikipediaController {
  private final WikipediaLookupService wikipediaLookupService;
  private final WikipediaRateLimiter wikipediaRateLimiter;

  public WikipediaController(
      WikipediaLookupService wikipediaLookupService,
      WikipediaRateLimiter wikipediaRateLimiter
  ) {
    this.wikipediaLookupService = wikipediaLookupService;
    this.wikipediaRateLimiter = wikipediaRateLimiter;
  }

  @GetMapping("/wikipedia/lookup")
  public ApiResponse<WikipediaLookupDTO> lookup(
      @RequestParam("q") @NotBlank @Size(max = 64) String q,
      @RequestParam(value = "offset", required = false) @Min(0) Integer offset,
      @RequestParam(value = "limit", required = false) @Min(1) @Max(8) Integer limit,
      HttpServletRequest request
  ) {
    wikipediaRateLimiter.check(clientKey(request));
    return ApiResponse.ok(
        RequestIdHolder.get(), wikipediaLookupService.lookup(q, offset, limit));
  }

  private static String clientKey(HttpServletRequest request) {
    if (request == null) {
      return "unknown";
    }
    String forwarded = request.getHeader("X-Forwarded-For");
    if (forwarded != null && !forwarded.isBlank()) {
      int comma = forwarded.indexOf(',');
      return (comma > 0 ? forwarded.substring(0, comma) : forwarded).trim();
    }
    String ip = request.getRemoteAddr();
    return ip == null || ip.isBlank() ? "unknown" : ip;
  }
}
