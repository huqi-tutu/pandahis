package com.pandahis.histomap.common.auth;

public final class UserContextHolder {
  private static final ThreadLocal<UserContext> CTX = ThreadLocal.withInitial(UserContext::anonymous);

  private UserContextHolder() {}

  public static UserContext get() {
    return CTX.get();
  }

  public static void set(UserContext userContext) {
    CTX.set(userContext);
  }

  public static void clear() {
    CTX.remove();
  }
}

