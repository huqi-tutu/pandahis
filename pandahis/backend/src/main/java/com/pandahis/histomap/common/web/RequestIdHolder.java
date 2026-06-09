package com.pandahis.histomap.common.web;

public final class RequestIdHolder {
  private static final ThreadLocal<String> REQUEST_ID = new ThreadLocal<>();

  private RequestIdHolder() {}

  public static void set(String requestId) {
    REQUEST_ID.set(requestId);
  }

  public static String get() {
    String v = REQUEST_ID.get();
    return v == null ? "" : v;
  }

  public static void clear() {
    REQUEST_ID.remove();
  }
}

