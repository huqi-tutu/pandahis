package com.pandahis.histomap.common.config;

import jakarta.annotation.PostConstruct;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "histomap")
public class HistomapProperties {
  private static final String DEFAULT_MINIAPP_APP_ID = "wx130cbdfbc6c4b1ab";
  private static final String DEFAULT_MINIAPP_APP_SECRET = "bd3eaaab354744ccdfda38dee822920a";

  private final Box box = new Box();
  private final WeChat weChat = new WeChat();
  private final Auth auth = new Auth();
  private final Wikipedia wikipedia = new Wikipedia();

  @PostConstruct
  void applyWeChatMiniappDefaults() {
    WeChat.Miniapp m = weChat.getMiniapp();
    if (m.getAppId() == null || m.getAppId().isBlank()) {
      m.setAppId(DEFAULT_MINIAPP_APP_ID);
    }
    if (m.getAppSecret() == null || m.getAppSecret().isBlank()) {
      m.setAppSecret(DEFAULT_MINIAPP_APP_SECRET);
    }
  }

  public Box getBox() {
    return box;
  }

  public WeChat getWeChat() {
    return weChat;
  }

  public Auth getAuth() {
    return auth;
  }

  public Wikipedia getWikipedia() {
    return wikipedia;
  }

  public static class WeChat {
    private final Miniapp miniapp = new Miniapp();

    public Miniapp getMiniapp() {
      return miniapp;
    }

    public static class Miniapp {
      /** 微信小程序 AppId */
      private String appId = "";
      /** 微信小程序 AppSecret（勿提交到仓库，生产用环境变量） */
      private String appSecret = "";

      public String getAppId() {
        return appId;
      }

      public void setAppId(String appId) {
        this.appId = appId;
      }

      public String getAppSecret() {
        return appSecret;
      }

      public void setAppSecret(String appSecret) {
        this.appSecret = appSecret;
      }
    }
  }

  public static class Auth {
    private final Jwt jwt = new Jwt();
    /**
     * 与请求 Bearer 完全一致时，在激活了 {@code dev} profile 下映射为测试用户 id=1。
     */
    private String devBypassToken = "dev-local-token";

    public Jwt getJwt() {
      return jwt;
    }

    public String getDevBypassToken() {
      return devBypassToken;
    }

    public void setDevBypassToken(String devBypassToken) {
      this.devBypassToken = devBypassToken;
    }

    public static class Jwt {
      /** HS256 密钥，至少 32 字节 */
      private String secret = "dev-only-change-me-32bytes-min________";
      private int expiresDays = 7;

      public String getSecret() {
        return secret;
      }

      public void setSecret(String secret) {
        this.secret = secret;
      }

      public int getExpiresDays() {
        return expiresDays;
      }

      public void setExpiresDays(int expiresDays) {
        this.expiresDays = expiresDays;
      }
    }
  }

  public static class Wikipedia {
    /** MediaWiki API 根地址 */
    private String apiBase = "https://zh.wikipedia.org/w/api.php";
    private String lang = "zh";
    private String userAgent = "PadanhisHistomap/1.0 (dictionary-lookup; contact: support@padanhis.local)";
    /** 可选 OAuth access token；为空则匿名访问 */
    private String accessToken = "";
    private int connectTimeoutSeconds = 8;
    private int requestTimeoutSeconds = 12;
    private int cacheTtlSeconds = 21600;
    private int maxExtractChars = 12000;
    private int defaultLimit = 3;
    private int maxLimit = 8;

    public String getApiBase() {
      return apiBase;
    }

    public void setApiBase(String apiBase) {
      this.apiBase = apiBase;
    }

    public String getLang() {
      return lang;
    }

    public void setLang(String lang) {
      this.lang = lang;
    }

    public String getUserAgent() {
      return userAgent;
    }

    public void setUserAgent(String userAgent) {
      this.userAgent = userAgent;
    }

    public String getAccessToken() {
      return accessToken;
    }

    public void setAccessToken(String accessToken) {
      this.accessToken = accessToken;
    }

    public int getConnectTimeoutSeconds() {
      return connectTimeoutSeconds;
    }

    public void setConnectTimeoutSeconds(int connectTimeoutSeconds) {
      this.connectTimeoutSeconds = connectTimeoutSeconds;
    }

    public int getRequestTimeoutSeconds() {
      return requestTimeoutSeconds;
    }

    public void setRequestTimeoutSeconds(int requestTimeoutSeconds) {
      this.requestTimeoutSeconds = requestTimeoutSeconds;
    }

    public int getCacheTtlSeconds() {
      return cacheTtlSeconds;
    }

    public void setCacheTtlSeconds(int cacheTtlSeconds) {
      this.cacheTtlSeconds = cacheTtlSeconds;
    }

    public int getMaxExtractChars() {
      return maxExtractChars;
    }

    public void setMaxExtractChars(int maxExtractChars) {
      this.maxExtractChars = maxExtractChars;
    }

    public int getDefaultLimit() {
      return defaultLimit;
    }

    public void setDefaultLimit(int defaultLimit) {
      this.defaultLimit = defaultLimit;
    }

    public int getMaxLimit() {
      return maxLimit;
    }

    public void setMaxLimit(int maxLimit) {
      this.maxLimit = maxLimit;
    }
  }

  public static class Box {
    private final Critiques critiques = new Critiques();
    private final Relics relics = new Relics();

    public Critiques getCritiques() {
      return critiques;
    }

    public Relics getRelics() {
      return relics;
    }
  }

  public static class Critiques {
    private int maxCount = 5;

    public int getMaxCount() {
      return maxCount;
    }

    public void setMaxCount(int maxCount) {
      this.maxCount = maxCount;
    }
  }

  public static class Relics {
    private int maxCount = 5;

    public int getMaxCount() {
      return maxCount;
    }

    public void setMaxCount(int maxCount) {
      this.maxCount = maxCount;
    }
  }
}
