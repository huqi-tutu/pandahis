package com.pandahis.histomap.common.web;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 5)
public class RequestIdFilter extends OncePerRequestFilter {
  public static final String HEADER_REQUEST_ID = "X-Request-Id";

  @Override
  protected void doFilterInternal(
      HttpServletRequest request,
      HttpServletResponse response,
      FilterChain filterChain
  ) throws ServletException, IOException {
    String incoming = request.getHeader(HEADER_REQUEST_ID);
    String requestId = (incoming == null || incoming.isBlank()) ? UUID.randomUUID().toString() : incoming;
    try {
      RequestIdHolder.set(requestId);
      response.setHeader(HEADER_REQUEST_ID, requestId);
      filterChain.doFilter(request, response);
    } finally {
      RequestIdHolder.clear();
    }
  }
}

