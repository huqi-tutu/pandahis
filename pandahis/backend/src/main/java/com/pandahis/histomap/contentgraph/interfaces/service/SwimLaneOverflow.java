package com.pandahis.histomap.contentgraph.interfaces.service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 泳道收起规则：仅当同一时期并发史略超过上限时才折叠，而非按泳道总条数截断。
 */
final class SwimLaneOverflow {
  static final int MAX_CONCURRENT = 10;

  record BarSlice(String boxId, String title, int start, int end, String priority) {}

  record Split(List<BarSlice> visible, List<BarSlice> extra) {}

  private SwimLaneOverflow() {}

  static Split split(List<BarSlice> bars) {
    if (bars.isEmpty()) {
      return new Split(List.of(), List.of());
    }
    if (maxConcurrent(bars) <= MAX_CONCURRENT) {
      return new Split(bars, List.of());
    }
    Set<String> hidden = hiddenIds(bars);
    List<BarSlice> visible = new ArrayList<>();
    List<BarSlice> extra = new ArrayList<>();
    for (BarSlice bar : bars) {
      if (hidden.contains(bar.boxId())) {
        extra.add(bar);
      } else {
        visible.add(bar);
      }
    }
    return new Split(visible, extra);
  }

  static int maxConcurrent(List<BarSlice> bars) {
    List<Event> events = new ArrayList<>();
    for (BarSlice bar : bars) {
      int end = bar.end() <= bar.start() ? bar.start() + 1 : bar.end();
      events.add(new Event(bar.start(), 1, bar.boxId()));
      events.add(new Event(end, -1, bar.boxId()));
    }
    events.sort(Comparator.comparingInt(Event::year).thenComparingInt(Event::delta));
    int active = 0;
    int max = 0;
    for (Event event : events) {
      active += event.delta();
      max = Math.max(max, active);
    }
    return max;
  }

  private static Set<String> hiddenIds(List<BarSlice> bars) {
    Map<String, BarSlice> byId = bars.stream()
        .collect(Collectors.toMap(BarSlice::boxId, Function.identity(), (a, b) -> a));

    List<Event> events = new ArrayList<>();
    for (BarSlice bar : bars) {
      int end = bar.end() <= bar.start() ? bar.start() + 1 : bar.end();
      events.add(new Event(bar.start(), 1, bar.boxId()));
      events.add(new Event(end, -1, bar.boxId()));
    }
    events.sort(Comparator.comparingInt(Event::year).thenComparingInt(Event::delta));

    Set<String> hidden = new HashSet<>();
    Set<String> active = new HashSet<>();
    for (Event event : events) {
      if (event.delta() == 1) {
        active.add(event.boxId());
        while (visibleCount(active, hidden) > MAX_CONCURRENT) {
          String victim = pickLowestPriority(active, hidden, byId);
          if (victim == null) {
            break;
          }
          hidden.add(victim);
        }
      } else {
        active.remove(event.boxId());
      }
    }
    return hidden;
  }

  private static long visibleCount(Set<String> active, Set<String> hidden) {
    return active.stream().filter(id -> !hidden.contains(id)).count();
  }

  private static String pickLowestPriority(
      Set<String> active,
      Set<String> hidden,
      Map<String, BarSlice> byId
  ) {
    return active.stream()
        .filter(id -> !hidden.contains(id))
        .max(Comparator
            .comparingInt((String id) -> priorityRank(byId.get(id).priority()))
            .thenComparing(id -> -byId.get(id).start())
            .thenComparing(id -> id))
        .orElse(null);
  }

  private static int priorityRank(String priority) {
    if ("p0".equals(priority)) return 0;
    if ("p1".equals(priority)) return 1;
    if ("p2".equals(priority)) return 2;
    return 3;
  }

  private record Event(int year, int delta, String boxId) {}
}
