package com.pandahis.histomap.common.web;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class RequestLoggingFilter extends OncePerRequestFilter {
  private static final Logger log = LoggerFactory.getLogger(RequestLoggingFilter.class);

  @Override
  protected void doFilterInternal(
      HttpServletRequest request,
      HttpServletResponse response,
      FilterChain filterChain
  ) throws ServletException, IOException {
    long startNs = System.nanoTime();
    String rid = RequestIdHolder.get();
    String method = request.getMethod();
    String uri = request.getRequestURI();
    String query = request.getQueryString();
    String fullPath = (query == null || query.isBlank()) ? uri : (uri + "?" + query);
    String remote = request.getRemoteAddr();

    try {
      filterChain.doFilter(request, response);
    } finally {
      long costMs = (System.nanoTime() - startNs) / 1_000_000;
      int status = response.getStatus();
      String outRid = RequestIdHolder.get();
      String requestId = (outRid == null || outRid.isBlank()) ? rid : outRid;
      log.info("[{}] {} {} -> {} ({}ms) ip={}", requestId, method, fullPath, status, costMs, remote);
    }
  }
}

