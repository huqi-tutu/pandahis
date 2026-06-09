package com.pandahis.histomap.common.api;

public class ApiException extends RuntimeException {
  private final ErrorCode code;

  public ApiException(ErrorCode code, String message) {
    super(message);
    this.code = code;
  }

  public ErrorCode getCode() {
    return code;
  }

  public static ApiException invalidArgument(String message) {
    return new ApiException(ErrorCode.INVALID_ARGUMENT, message);
  }

  public static ApiException unauthorized(String message) {
    return new ApiException(ErrorCode.UNAUTHORIZED, message);
  }

  public static ApiException forbidden(String message) {
    return new ApiException(ErrorCode.FORBIDDEN, message);
  }

  public static ApiException notFound(String message) {
    return new ApiException(ErrorCode.NOT_FOUND, message);
  }

  public static ApiException internalError(String message) {
    return new ApiException(ErrorCode.INTERNAL_ERROR, message);
  }
}

