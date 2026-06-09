package com.pandahis.histomap.common.auth;

import com.pandahis.histomap.common.api.ApiException;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

@Aspect
@Component
public class RequireAuthAspect {
  @Around("@within(com.pandahis.histomap.common.auth.RequireAuth) || @annotation(com.pandahis.histomap.common.auth.RequireAuth)")
  public Object around(ProceedingJoinPoint pjp) throws Throwable {
    UserContext ctx = UserContextHolder.get();
    if (ctx == null || !ctx.authenticated() || ctx.userId() == null) {
      throw ApiException.unauthorized("login required");
    }
    return pjp.proceed();
  }
}

