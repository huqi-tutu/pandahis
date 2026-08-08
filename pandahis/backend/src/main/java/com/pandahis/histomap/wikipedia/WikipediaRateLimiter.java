package com.pandahis.histomap.wikipedia;

import com.pandahis.histomap.common.api.ApiException;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

/** 简易滑动窗口限流：按客户端标识限制维基查询频率。 */
@Component
public class WikipediaRateLimiter {
  private static final int MAX_REQUESTS_PER_WINDOW = 30;
  private static final long WINDOW_MS = 60_000L;
  private static final int MAX_TRACKED_KEYS = 2_000;

  private final ConcurrentHashMap<String, Deque<Long>> hits = new ConcurrentHashMap<>();

  public void check(String clientKey) {
    String key = (clientKey == null || clientKey.isBlank()) ? "unknown" : clientKey.trim();
    long now = System.currentTimeMillis();
    Deque<Long> q = hits.computeIfAbsent(key, k -> new ArrayDeque<>());
    synchronized (q) {
      while (!q.isEmpty() && now - q.peekFirst() >= WINDOW_MS) {
        q.pollFirst();
      }
      if (q.size() >= MAX_REQUESTS_PER_WINDOW) {
        throw ApiException.rateLimited("查询过于频繁，请稍后再试");
      }
      q.addLast(now);
    }
    if (hits.size() > MAX_TRACKED_KEYS) {
      evictStale(now);
    }
  }

  private void evictStale(long now) {
    Iterator<Map.Entry<String, Deque<Long>>> it = hits.entrySet().iterator();
    while (it.hasNext() && hits.size() > MAX_TRACKED_KEYS / 2) {
      Map.Entry<String, Deque<Long>> e = it.next();
      Deque<Long> q = e.getValue();
      synchronized (q) {
        while (!q.isEmpty() && now - q.peekFirst() >= WINDOW_MS) {
          q.pollFirst();
        }
        if (q.isEmpty()) {
          it.remove();
        }
      }
    }
  }
}
