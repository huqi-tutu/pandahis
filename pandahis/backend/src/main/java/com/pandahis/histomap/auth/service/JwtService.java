package com.pandahis.histomap.auth.service;

import com.pandahis.histomap.common.config.HistomapProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Service;

@Service
public class JwtService {
  private final HistomapProperties histomapProperties;
  private SecretKey key;

  public JwtService(HistomapProperties histomapProperties) {
    this.histomapProperties = histomapProperties;
  }

  @PostConstruct
  void init() {
    String secret = histomapProperties.getAuth().getJwt().getSecret();
    byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
    if (bytes.length < 32) {
      throw new IllegalStateException("histomap.auth.jwt.secret must be at least 32 bytes for HS256");
    }
    this.key = Keys.hmacShaKeyFor(bytes);
  }

  public String sign(long userId) {
    int days = Math.max(1, histomapProperties.getAuth().getJwt().getExpiresDays());
    Instant now = Instant.now();
    Instant exp = now.plus(days, ChronoUnit.DAYS);
    return Jwts.builder()
        .subject(String.valueOf(userId))
        .issuedAt(Date.from(now))
        .expiration(Date.from(exp))
        .signWith(key)
        .compact();
  }

  /**
   * @return userId if valid, otherwise {@code null}
   */
  public Long parseUserId(String token) {
    if (token == null || token.isBlank()) {
      return null;
    }
    try {
      Claims claims = Jwts.parser()
          .verifyWith(key)
          .build()
          .parseSignedClaims(token)
          .getPayload();
      return Long.parseLong(claims.getSubject());
    } catch (JwtException | NumberFormatException e) {
      return null;
    }
  }
}
