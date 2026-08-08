package com.pandahis.histomap.wikipedia;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.pandahis.histomap.wikipedia.interfaces.WikipediaController;
import com.pandahis.histomap.wikipedia.interfaces.dto.WikipediaLookupDTO;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.FilterType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(
    controllers = WikipediaController.class,
    excludeFilters = @ComponentScan.Filter(
        type = FilterType.ASSIGNABLE_TYPE,
        classes = com.pandahis.histomap.common.auth.BearerAuthFilter.class
    )
)
@AutoConfigureMockMvc(addFilters = false)
class WikipediaApiTest {

  @Autowired
  private MockMvc mockMvc;

  @MockBean
  private WikipediaLookupService wikipediaLookupService;

  @MockBean
  private com.pandahis.histomap.wikipedia.WikipediaRateLimiter wikipediaRateLimiter;

  @Test
  void lookup_returnsParagraphPageWithoutPageUrl() throws Exception {
    when(wikipediaLookupService.lookup(eq("禅让制"), eq(0), eq(3)))
        .thenReturn(
            new WikipediaLookupDTO(
                "禅让制",
                true,
                "禅让制",
                List.of("第一段。", "第二段。", "第三段。"),
                0,
                3,
                true,
                4));

    mockMvc.perform(get("/wikipedia/lookup").param("q", "禅让制").param("offset", "0").param("limit", "3"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.query").value("禅让制"))
        .andExpect(jsonPath("$.data.found").value(true))
        .andExpect(jsonPath("$.data.resolvedTitle").value("禅让制"))
        .andExpect(jsonPath("$.data.paragraphs.length()").value(3))
        .andExpect(jsonPath("$.data.hasMore").value(true))
        .andExpect(jsonPath("$.data.nextOffset").value(3))
        .andExpect(jsonPath("$.data.totalParagraphs").value(4))
        .andExpect(jsonPath("$.data.pageUrl").doesNotExist());
  }

  @Test
  void lookup_notFound_returnsFoundFalse() throws Exception {
    when(wikipediaLookupService.lookup(eq("不存在xyz"), isNull(), isNull()))
        .thenReturn(new WikipediaLookupDTO("不存在xyz", false, null, List.of(), 0, null, false, 0));

    mockMvc.perform(get("/wikipedia/lookup").param("q", "不存在xyz"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.found").value(false))
        .andExpect(jsonPath("$.data.paragraphs.length()").value(0))
        .andExpect(jsonPath("$.data.hasMore").value(false));
  }
}
