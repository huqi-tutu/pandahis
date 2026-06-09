package com.pandahis.histomap.common.auth;

public record UserContext(Long userId, boolean authenticated) {
  public static UserContext anonymous() {
    return new UserContext(null, false);
  }
}

