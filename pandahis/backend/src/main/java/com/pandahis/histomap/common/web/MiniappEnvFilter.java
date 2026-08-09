package com.pandahis.histomap.common.web;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 读取小程序请求头 {@link ClientEnvContext#HEADER_MINIAPP_ENV}，
 * 供功能开关等按 develop / trial / release 分流。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 6)
public class MiniappEnvFilter extends OncePerRequestFilter {

  @Override
  protected void doFilterInternal(
      HttpServletRequest request,
      HttpServletResponse response,
      FilterChain filterChain
  ) throws ServletException, IOException {
    ClientEnvContext.set(request.getHeader(ClientEnvContext.HEADER_MINIAPP_ENV));
    try {
      filterChain.doFilter(request, response);
    } finally {
      ClientEnvContext.clear();
    }
  }
}
