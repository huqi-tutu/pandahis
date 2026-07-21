package com.pandahis.histomap.dictionary.domain;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

@Component
public class UnihanPinyinStore {
  private static final Logger log = LoggerFactory.getLogger(UnihanPinyinStore.class);
  private static final String RESOURCE = "dictionary/unihan-pinyin.json";

  private final ObjectMapper objectMapper;
  private final Map<String, String> pinyinByChar = new HashMap<>();

  public UnihanPinyinStore(ObjectMapper objectMapper) {
    this.objectMapper = objectMapper;
    load();
  }

  public String findPinyin(String ch) {
    if (ch == null || ch.isEmpty()) {
      return null;
    }
    return pinyinByChar.get(ch);
  }

  public int entryCount() {
    return pinyinByChar.size();
  }

  public Map<String, String> pinyinView() {
    return Collections.unmodifiableMap(pinyinByChar);
  }

  private void load() {
    ClassPathResource resource = new ClassPathResource(RESOURCE);
    if (!resource.exists()) {
      log.warn("Unihan pinyin resource missing: {}", RESOURCE);
      return;
    }
    try (InputStream in = resource.getInputStream()) {
      Bundle bundle = objectMapper.readValue(in, Bundle.class);
      pinyinByChar.clear();
      if (bundle.pinyin != null) {
        pinyinByChar.putAll(bundle.pinyin);
      }
      log.info("Loaded Unihan pinyin: {} entries", pinyinByChar.size());
    } catch (IOException e) {
      throw new IllegalStateException("Failed to load Unihan pinyin resource: " + RESOURCE, e);
    }
  }

  @JsonIgnoreProperties(ignoreUnknown = true)
  private static final class Bundle {
    public Map<String, String> pinyin;
  }
}
