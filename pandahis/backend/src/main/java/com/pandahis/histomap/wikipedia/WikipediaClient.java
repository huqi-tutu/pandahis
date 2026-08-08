package com.pandahis.histomap.wikipedia;

import java.util.Optional;

public interface WikipediaClient {
  /**
   * 按用户检索词解析词条并返回清洗后的段落列表。
   * 无命中时返回 empty；网络/上游错误应抛出异常由 Service 降级。
   */
  Optional<WikipediaArticle> fetchArticle(String query);
}
