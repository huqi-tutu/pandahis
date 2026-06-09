package com.pandahis.histomap.common.api;

public record ApiResponse<T>(String code, String message, String requestId, T data) {
  public static <T> ApiResponse<T> ok(String requestId, T data) {
    return new ApiResponse<>("OK", "success", requestId, data);
  }
}

