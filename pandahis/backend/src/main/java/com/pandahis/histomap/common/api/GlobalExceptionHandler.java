package com.pandahis.histomap.common.api;

import com.pandahis.histomap.common.web.RequestIdHolder;
import jakarta.validation.ConstraintViolationException;
import java.io.IOException;
import java.util.Objects;
import java.util.stream.Collectors;
import org.apache.catalina.connector.ClientAbortException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.async.AsyncRequestNotUsableException;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
public class GlobalExceptionHandler {
  private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

  @ExceptionHandler(ApiException.class)
  public ResponseEntity<ApiResponse<Object>> handleApiException(ApiException ex) {
    String requestId = RequestIdHolder.get();
    log.warn("[{}] ApiException code={} msg={}", requestId, ex.getCode(), ex.getMessage());
    HttpStatus status = switch (ex.getCode()) {
      case INVALID_ARGUMENT -> HttpStatus.BAD_REQUEST;
      case UNAUTHORIZED -> HttpStatus.UNAUTHORIZED;
      case FORBIDDEN -> HttpStatus.FORBIDDEN;
      case NOT_FOUND -> HttpStatus.NOT_FOUND;
      case CONFLICT -> HttpStatus.CONFLICT;
      case RATE_LIMITED -> HttpStatus.TOO_MANY_REQUESTS;
      case INTERNAL_ERROR -> HttpStatus.INTERNAL_SERVER_ERROR;
    };
    return ResponseEntity.status(status)
        .body(new ApiResponse<>(ex.getCode().name(), ex.getMessage(), requestId, null));
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<ApiResponse<Object>> handleValidation(MethodArgumentNotValidException ex) {
    String requestId = RequestIdHolder.get();
    String msg = ex.getBindingResult()
        .getFieldErrors()
        .stream()
        .map(this::formatFieldError)
        .collect(Collectors.joining("; "));
    log.warn("[{}] ValidationError {}", requestId, msg);
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ApiResponse<>(ErrorCode.INVALID_ARGUMENT.name(), msg, requestId, null));
  }

  @ExceptionHandler(ConstraintViolationException.class)
  public ResponseEntity<ApiResponse<Object>> handleConstraintViolation(ConstraintViolationException ex) {
    String requestId = RequestIdHolder.get();
    log.warn("[{}] ConstraintViolation {}", requestId, ex.getMessage());
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ApiResponse<>(ErrorCode.INVALID_ARGUMENT.name(), ex.getMessage(), requestId, null));
  }

  @ExceptionHandler(HandlerMethodValidationException.class)
  public ResponseEntity<ApiResponse<Object>> handleHandlerMethodValidation(HandlerMethodValidationException ex) {
    String requestId = RequestIdHolder.get();
    String msg = ex.getAllValidationResults().stream()
        .flatMap(result -> result.getResolvableErrors().stream())
        .map(err -> err.getDefaultMessage() == null ? "invalid" : err.getDefaultMessage())
        .filter(Objects::nonNull)
        .distinct()
        .collect(Collectors.joining("; "));
    if (msg.isBlank()) {
      msg = "invalid request parameters";
    }
    log.warn("[{}] HandlerMethodValidation {}", requestId, msg);
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ApiResponse<>(ErrorCode.INVALID_ARGUMENT.name(), msg, requestId, null));
  }

  @ExceptionHandler(NoResourceFoundException.class)
  public ResponseEntity<ApiResponse<Object>> handleNoResourceFound(NoResourceFoundException ex) {
    String requestId = RequestIdHolder.get();
    log.warn("[{}] NoResourceFound {}", requestId, ex.getResourcePath());
    return ResponseEntity.status(HttpStatus.NOT_FOUND)
        .body(new ApiResponse<>(ErrorCode.NOT_FOUND.name(), "not found", requestId, null));
  }

  /**
   * 客户端在响应写回完成前关闭连接（取消请求、切页、模拟器重载、超时等）。非业务错误，避免打成 UnhandledException。
   */
  @ExceptionHandler(ClientAbortException.class)
  public ResponseEntity<Void> handleClientAbort() {
    log.debug("[{}] client disconnected during response write", RequestIdHolder.get());
    return ResponseEntity.noContent().build();
  }

  @ExceptionHandler(AsyncRequestNotUsableException.class)
  public ResponseEntity<?> handleAsyncNotUsable(AsyncRequestNotUsableException ex) {
    String requestId = RequestIdHolder.get();
    if (isCausedByClientAbort(ex)) {
      log.debug("[{}] client disconnected during response write", requestId);
      return ResponseEntity.noContent().build();
    }
    log.error("[{}] AsyncRequestNotUsableException", requestId, ex);
    return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
        .body(new ApiResponse<>(ErrorCode.INTERNAL_ERROR.name(), "internal error", requestId, null));
  }

  @ExceptionHandler(Exception.class)
  public ResponseEntity<?> handleOther(Exception ex) {
    String requestId = RequestIdHolder.get();
    if (isCausedByClientAbort(ex)) {
      log.debug("[{}] client disconnected during response write", requestId);
      return ResponseEntity.noContent().build();
    }
    log.error("[{}] UnhandledException", requestId, ex);
    return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
        .body(new ApiResponse<>(ErrorCode.INTERNAL_ERROR.name(), "internal error", requestId, null));
  }

  private static boolean isCausedByClientAbort(Throwable ex) {
    for (Throwable t = ex; t != null; t = t.getCause()) {
      if (t instanceof ClientAbortException) {
        return true;
      }
      if (t instanceof IOException) {
        String m = t.getMessage();
        if (m != null
            && (m.contains("中止")
                || m.contains("Connection reset")
                || m.contains("Broken pipe")
                || m.contains("Connection aborted"))) {
          return true;
        }
      }
    }
    return false;
  }

  private String formatFieldError(FieldError fe) {
    return fe.getField() + " " + (fe.getDefaultMessage() == null ? "invalid" : fe.getDefaultMessage());
  }
}

