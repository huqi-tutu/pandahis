package com.pandahis.histomap.common.auth;

import com.pandahis.histomap.auth.service.JwtService;
import com.pandahis.histomap.common.config.HistomapProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Arrays;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(2)
public class BearerAuthFilter extends OncePerRequestFilter {
  private static final long DEV_BYPASS_USER_ID = 1L;

  private final JwtService jwtService;
  private final HistomapProperties histomapProperties;
  private final Environment environment;

  public BearerAuthFilter(JwtService jwtService, HistomapProperties histomapProperties, Environment environment) {
    this.jwtService = jwtService;
    this.histomapProperties = histomapProperties;
    this.environment = environment;
  }

  @Override
  protected void doFilterInternal(
      HttpServletRequest request,
      HttpServletResponse response,
      FilterChain filterChain
  ) throws ServletException, IOException {
    String auth = request.getHeader("Authorization");
    try {
      UserContextHolder.set(parse(auth));
      filterChain.doFilter(request, response);
    } finally {
      UserContextHolder.clear();
    }
  }

  private UserContext parse(String authHeader) {
    if (authHeader == null || authHeader.isBlank()) {
      return UserContext.anonymous();
    }
    if (!authHeader.startsWith("Bearer ")) {
      return UserContext.anonymous();
    }
    String token = authHeader.substring("Bearer ".length()).trim();
    if (token.isEmpty()) {
      return UserContext.anonymous();
    }

    if (isDevProfileActive()) {
      String bypass = histomapProperties.getAuth().getDevBypassToken();
      if (bypass != null && !bypass.isBlank() && bypass.equals(token)) {
        return new UserContext(DEV_BYPASS_USER_ID, true);
      }
    }

    Long userId = jwtService.parseUserId(token);
    if (userId == null) {
      return UserContext.anonymous();
    }
    return new UserContext(userId, true);
  }

  private boolean isDevProfileActive() {
    return Arrays.stream(environment.getActiveProfiles()).anyMatch("dev"::equals);
  }
}
