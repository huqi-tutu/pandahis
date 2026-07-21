package com.pandahis.histomap.dictionary;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles({"test", "dev"})
class DictionaryApiTest {

  @Autowired
  private MockMvc mockMvc;

  @Test
  void lookup_singleChar_returnsPinyin() throws Exception {
    mockMvc.perform(get("/dictionary/lookup").param("q", "帝"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.entries.length()").value(1))
        .andExpect(jsonPath("$.data.entries[0].character").value("帝"))
        .andExpect(jsonPath("$.data.entries[0].pinyin").value("dì"));
  }

  @Test
  void lookup_multiChars_returnsPinyinInOrder() throws Exception {
    mockMvc.perform(get("/dictionary/lookup").param("q", "嫘祖"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.code").value("OK"))
        .andExpect(jsonPath("$.data.entries.length()").value(2))
        .andExpect(jsonPath("$.data.entries[0].character").value("嫘"))
        .andExpect(jsonPath("$.data.entries[0].pinyin").value("léi"))
        .andExpect(jsonPath("$.data.entries[1].character").value("祖"))
        .andExpect(jsonPath("$.data.entries[1].pinyin").value("zǔ"));
  }

  @Test
  void lookup_rareChars_returnsPinyin() throws Exception {
    mockMvc.perform(get("/dictionary/lookup").param("q", "嫫母"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.entries.length()").value(2))
        .andExpect(jsonPath("$.data.entries[0].character").value("嫫"))
        .andExpect(jsonPath("$.data.entries[0].pinyin").value("mó"))
        .andExpect(jsonPath("$.data.entries[1].character").value("母"))
        .andExpect(jsonPath("$.data.entries[1].pinyin").value("mǔ"));
  }
}
