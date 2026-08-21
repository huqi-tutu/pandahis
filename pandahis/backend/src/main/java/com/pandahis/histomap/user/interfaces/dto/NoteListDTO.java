package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record NoteListDTO(int page, int pageSize, long total, List<Item> items) {
  public record Item(
      long id,
      String boxId,
      String boxTitle,
      String selectedText,
      String noteText,
      String createdAt
  ) {}
}
