package com.pandahis.histomap.wikipedia;

import com.pandahis.histomap.common.config.HistomapProperties;
import com.pandahis.histomap.wikipedia.interfaces.dto.WikipediaLookupDTO;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class WikipediaLookupService {
  private static final Logger log = LoggerFactory.getLogger(WikipediaLookupService.class);
  private static final int MAX_CACHE_ENTRIES = 256;
  private static final long ERROR_NEGATIVE_TTL_MS = 60_000L;

  private final WikipediaClient wikipediaClient;
  private final HistomapProperties props;
  private final Map<String, CacheEntry> cache =
      new LinkedHashMap<>(64, 0.75f, true) {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, CacheEntry> eldest) {
          return size() > MAX_CACHE_ENTRIES;
        }
      };

  public WikipediaLookupService(WikipediaClient wikipediaClient, HistomapProperties props) {
    this.wikipediaClient = wikipediaClient;
    this.props = props;
  }

  public WikipediaLookupDTO lookup(String query, Integer offsetParam, Integer limitParam) {
    String trimmed = query == null ? "" : query.trim();
    if (trimmed.isEmpty()) {
      return empty(trimmed, 0);
    }

    int offset = offsetParam == null || offsetParam < 0 ? 0 : offsetParam;
    int defaultLimit = Math.max(1, props.getWikipedia().getDefaultLimit());
    int maxLimit = Math.max(defaultLimit, props.getWikipedia().getMaxLimit());
    int limit = limitParam == null ? defaultLimit : Math.min(Math.max(1, limitParam), maxLimit);

    Optional<WikipediaArticle> article;
    try {
      article = loadArticle(trimmed);
    } catch (RuntimeException ex) {
      log.warn("wikipedia lookup degraded query={} reason={}", trimmed, ex.toString());
      putCache(trimmed, null, ERROR_NEGATIVE_TTL_MS);
      return empty(trimmed, offset);
    }

    if (article.isEmpty()) {
      return empty(trimmed, offset);
    }

    List<String> all = article.get().paragraphs();
    int total = all.size();
    if (offset >= total) {
      return new WikipediaLookupDTO(
          trimmed,
          true,
          article.get().resolvedTitle(),
          List.of(),
          offset,
          null,
          false,
          total);
    }

    int end = Math.min(offset + limit, total);
    List<String> page = all.subList(offset, end);
    boolean hasMore = end < total;
    Integer nextOffset = hasMore ? end : null;

    return new WikipediaLookupDTO(
        trimmed,
        true,
        article.get().resolvedTitle(),
        List.copyOf(page),
        offset,
        nextOffset,
        hasMore,
        total);
  }

  private Optional<WikipediaArticle> loadArticle(String query) {
    long now = System.currentTimeMillis();
    synchronized (cache) {
      CacheEntry cached = cache.get(query);
      if (cached != null) {
        if (cached.expiresAtMs() > now) {
          return Optional.ofNullable(cached.article());
        }
        cache.remove(query);
      }
    }

    Optional<WikipediaArticle> fetched = wikipediaClient.fetchArticle(query);
    long ttlMs = Math.max(60, props.getWikipedia().getCacheTtlSeconds()) * 1000L;
    if (fetched.isPresent()) {
      putCache(query, fetched.get(), ttlMs);
    } else {
      putCache(query, null, Math.min(ttlMs, 5 * 60_000L));
    }
    return fetched;
  }

  private void putCache(String query, WikipediaArticle article, long ttlMs) {
    synchronized (cache) {
      cache.put(query, new CacheEntry(article, System.currentTimeMillis() + ttlMs));
    }
  }

  private static WikipediaLookupDTO empty(String query, int offset) {
    return new WikipediaLookupDTO(query, false, null, List.of(), offset, null, false, 0);
  }

  private record CacheEntry(WikipediaArticle article, long expiresAtMs) {}
}
