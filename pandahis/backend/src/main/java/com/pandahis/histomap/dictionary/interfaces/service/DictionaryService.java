package com.pandahis.histomap.dictionary.interfaces.service;

import com.pandahis.histomap.dictionary.domain.UnihanPinyinStore;
import com.pandahis.histomap.dictionary.interfaces.dto.DictionaryEntryDTO;
import com.pandahis.histomap.dictionary.interfaces.dto.DictionaryLookupDTO;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class DictionaryService {
  private static final int MAX_CHARS = 8;

  private final UnihanPinyinStore unihanPinyinStore;

  public DictionaryService(UnihanPinyinStore unihanPinyinStore) {
    this.unihanPinyinStore = unihanPinyinStore;
  }

  public DictionaryLookupDTO lookup(String query) {
    String trimmed = query == null ? "" : query.trim();
    List<String> chars = extractHanChars(trimmed);
    List<DictionaryEntryDTO> entries = new ArrayList<>();

    for (String ch : chars) {
      entries.add(new DictionaryEntryDTO(ch, unihanPinyinStore.findPinyin(ch)));
    }

    return new DictionaryLookupDTO(trimmed, entries);
  }

  private static List<String> extractHanChars(String text) {
    List<String> chars = new ArrayList<>();
    if (text.isEmpty()) {
      return chars;
    }
    text.codePoints()
        .filter(DictionaryService::isHanCodePoint)
        .limit(MAX_CHARS)
        .forEach(cp -> chars.add(new String(Character.toChars(cp))));
    return chars;
  }

  private static boolean isHanCodePoint(int codePoint) {
    Character.UnicodeScript script = Character.UnicodeScript.of(codePoint);
    return script == Character.UnicodeScript.HAN;
  }
}
