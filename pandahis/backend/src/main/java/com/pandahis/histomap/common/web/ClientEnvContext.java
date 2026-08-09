package com.pandahis.histomap.common.web;

/** 当前请求对应的小程序运行环境（develop / trial / release），由 {@link MiniappEnvFilter} 注入。 */
public final class ClientEnvContext {
  public static final String HEADER_MINIAPP_ENV = "X-Miniapp-Env";
  public static final String ENV_DEVELOP = "develop";

  private static final ThreadLocal<String> CURRENT = new ThreadLocal<>();

  private ClientEnvContext() {}

  public static void set(String envVersion) {
    if (envVersion == null || envVersion.isBlank()) {
      CURRENT.remove();
      return;
    }
    CURRENT.set(envVersion.trim().toLowerCase());
  }

  public static String get() {
    return CURRENT.get();
  }

  public static boolean isDevelop() {
    return ENV_DEVELOP.equals(get());
  }

  public static void clear() {
    CURRENT.remove();
  }
}
