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
    private int maxCount = 3;

    public int getMaxCount() {
      return maxCount;
    }

    public void setMaxCount(int maxCount) {
      this.maxCount = maxCount;
    }
  }
}
