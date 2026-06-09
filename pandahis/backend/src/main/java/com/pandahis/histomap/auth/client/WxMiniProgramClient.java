package com.pandahis.histomap.auth.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.config.HistomapProperties;
import java.io.IOException;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.util.UriComponentsBuilder;

@Component
public class WxMiniProgramClient {
  private final RestClient restClient;
  private final HistomapProperties histomapProperties;
  private final ObjectMapper objectMapper;

  public WxMiniProgramClient(
      RestClient.Builder restClientBuilder,
      HistomapProperties histomapProperties,
      ObjectMapper objectMapper
  ) {
    this.restClient = restClientBuilder.baseUrl("https://api.weixin.qq.com").build();
    this.histomapProperties = histomapProperties;
    this.objectMapper = objectMapper;
  }

  public WxCode2SessionResult code2Session(String jsCode) {
    String appId = histomapProperties.getWeChat().getMiniapp().getAppId();
    String secret = histomapProperties.getWeChat().getMiniapp().getAppSecret();
    if (appId == null || appId.isBlank() || secret == null || secret.isBlank()) {
      throw ApiException.internalError("WeChat miniapp app-id/app-secret is not configured");
    }

    String uri = UriComponentsBuilder.fromPath("/sns/jscode2session")
        .queryParam("appid", appId)
        .queryParam("secret", secret)
        .queryParam("js_code", jsCode)
        .queryParam("grant_type", "authorization_code")
        .build(true)
        .toUriString();

    String raw = restClient.get()
        .uri(uri)
        .retrieve()
        .body(String.class);

    if (raw == null || raw.isBlank()) {
      throw ApiException.internalError("empty response from WeChat jscode2session");
    }

    JsonNode root;
    try {
      root = objectMapper.readTree(raw);
    } catch (IOException e) {
      throw ApiException.internalError("invalid JSON from WeChat jscode2session");
    }

    if (root.hasNonNull("errcode") && root.get("errcode").asInt() != 0) {
      int err = root.get("errcode").asInt();
      String msg = root.hasNonNull("errmsg") ? root.get("errmsg").asText() : "wechat error";
      if (err == 40029 || err == 40163) {
        throw ApiException.invalidArgument("invalid or expired wx.login code: " + msg);
      }
      throw ApiException.internalError("WeChat jscode2session failed: " + err + " " + msg);
    }

    String openid = textOrNull(root, "openid");
    if (openid == null || openid.isBlank()) {
      throw ApiException.internalError("WeChat response missing openid");
    }
    String sessionKey = textOrNull(root, "session_key");
    if (sessionKey == null || sessionKey.isBlank()) {
      throw ApiException.internalError("WeChat response missing session_key");
    }
    String unionid = textOrNull(root, "unionid");
    return new WxCode2SessionResult(openid, sessionKey, unionid);
  }

  private static String textOrNull(JsonNode root, String field) {
    if (!root.has(field) || root.get(field).isNull()) {
      return null;
    }
    return root.get(field).asText();
  }
}
