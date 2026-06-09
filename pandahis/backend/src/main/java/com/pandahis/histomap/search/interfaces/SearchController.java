package com.pandahis.histomap.search.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.search.interfaces.dto.SearchResultDTO;
import com.pandahis.histomap.search.interfaces.dto.SearchSuggestDTO;
import com.pandahis.histomap.search.interfaces.service.SearchService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping
public class SearchController {
  private final SearchService searchService;

  public SearchController(SearchService searchService) {
    this.searchService = searchService;
  }

  @GetMapping("/search/suggest")
  public ApiResponse<SearchSuggestDTO> suggest() {
    Long userId = UserContextHolder.get().authenticated() ? UserContextHolder.get().userId() : null;
    return ApiResponse.ok(RequestIdHolder.get(), searchService.suggest(userId));
  }

  @GetMapping("/search")
  public ApiResponse<SearchResultDTO> search(
      @RequestParam("q") @NotBlank @Size(max = 32) String q,
      @RequestParam(defaultValue = "1") @Min(1) int page,
      @RequestParam(defaultValue = "20") @Min(1) @Max(50) int pageSize
  ) {
    Long userId = UserContextHolder.get().authenticated() ? UserContextHolder.get().userId() : null;
    return ApiResponse.ok(RequestIdHolder.get(), searchService.search(userId, q, page, pageSize));
  }

  @RequireAuth
  @DeleteMapping("/search/history")
  public ApiResponse<Map<String, Object>> deleteHistory(@RequestParam("keyword") @NotBlank @Size(max = 64) String keyword) {
    searchService.deleteHistory(UserContextHolder.get().userId(), keyword);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }
}

