package com.pandahis.histomap.dictionary.interfaces.dto;

import java.util.List;

public record DictionaryLookupDTO(
    String query,
    List<DictionaryEntryDTO> entries
) {}
