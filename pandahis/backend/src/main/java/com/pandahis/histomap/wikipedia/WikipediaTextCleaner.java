package com.pandahis.histomap.wikipedia;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** 维基纯文本清洗与分段（供查阅浮窗使用）。 */
public final class WikipediaTextCleaner {
  private static final Pattern PINYIN_LABEL_PAREN =
      Pattern.compile("[（(][^）)]*拼音[：:][^）)]*[）)]");
  private static final Pattern ZHUYIN_LABEL_PAREN =
      Pattern.compile("[（(][^）)]*注音[：:][^）)]*[）)]");
  /** 括号内主要为带调拉丁拼音，如（zhuō）（shàn） */
  private static final Pattern INLINE_LATIN_PINYIN_PAREN =
      Pattern.compile(
          "[（(][a-zA-ZāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙǕǗǙǛÜ\\s·.-]+[）)]");
  private static final Pattern MULTI_BLANK_LINES = Pattern.compile("\\n{3,}");
  private static final Pattern MULTI_SPACES = Pattern.compile("[ \\t]{2,}");

  private WikipediaTextCleaner() {}

  public static String clean(String text) {
    if (text == null || text.isBlank()) {
      return "";
    }
    String out = text;
    out = PINYIN_LABEL_PAREN.matcher(out).replaceAll("");
    out = ZHUYIN_LABEL_PAREN.matcher(out).replaceAll("");
    out = INLINE_LATIN_PINYIN_PAREN.matcher(out).replaceAll("");
    out = out.replace('\u00a0', ' ');
    out = MULTI_SPACES.matcher(out).replaceAll(" ");
    out = MULTI_BLANK_LINES.matcher(out).replaceAll("\n\n");
    return out.trim();
  }

  public static List<String> toParagraphs(String text) {
    String cleaned = clean(text);
    if (cleaned.isEmpty()) {
      return List.of();
    }
    String[] parts = cleaned.split("\\n\\s*\\n");
    List<String> paragraphs = new ArrayList<>();
    for (String part : parts) {
      String p = part.replace('\n', ' ').replaceAll("\\s+", " ").trim();
      if (!p.isEmpty()) {
        paragraphs.add(p);
      }
    }
    return List.copyOf(paragraphs);
  }
}
