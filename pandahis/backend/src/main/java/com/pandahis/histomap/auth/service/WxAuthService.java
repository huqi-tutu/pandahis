package com.pandahis.histomap.auth.service;

import com.pandahis.histomap.auth.client.WxCode2SessionResult;
import com.pandahis.histomap.auth.client.WxMiniProgramClient;
import com.pandahis.histomap.auth.interfaces.dto.WxLoginResponse;
import com.pandahis.histomap.common.config.HistomapProperties;
import com.pandahis.histomap.invite.service.InviteService;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WxAuthService {
  private final WxMiniProgramClient wxMiniProgramClient;
  private final JwtService jwtService;
  private final HistomapProperties histomapProperties;
  private final JdbcTemplate jdbcTemplate;
  private final InviteService inviteService;

  public WxAuthService(
      WxMiniProgramClient wxMiniProgramClient,
      JwtService jwtService,
      HistomapProperties histomapProperties,
      JdbcTemplate jdbcTemplate,
      InviteService inviteService
  ) {
    this.wxMiniProgramClient = wxMiniProgramClient;
    this.jwtService = jwtService;
    this.histomapProperties = histomapProperties;
    this.jdbcTemplate = jdbcTemplate;
    this.inviteService = inviteService;
  }

  @Transactional
  public WxLoginResponse loginWithWxCode(String code, String inviteCode) {
    WxCode2SessionResult wx = wxMiniProgramClient.code2Session(code);
    UserUpsertResult upsert = findOrCreateUser(wx.openid(), wx.unionid());
    boolean inviteRecorded = false;
    if (upsert.createdNew()) {
      inviteRecorded = inviteService.recordNewUserFromInvite(upsert.userId(), inviteCode);
    }
    String accessToken = jwtService.sign(upsert.userId());
    int days = Math.max(1, histomapProperties.getAuth().getJwt().getExpiresDays());
    return new WxLoginResponse(
        accessToken,
        days * 24 * 60 * 60,
        upsert.createdNew(),
        inviteRecorded
    );
  }

  private record UserUpsertResult(long userId, boolean createdNew) {}

  private UserUpsertResult findOrCreateUser(String openid, String unionid) {
    List<Long> ids = jdbcTemplate.query(
        "SELECT id FROM app_user WHERE wx_openid = ?",
        (rs, i) -> rs.getLong(1),
        openid);
    Instant now = Instant.now();
    Timestamp ts = Timestamp.from(now);
    String union = emptyToNull(unionid);
    if (!ids.isEmpty()) {
      long id = ids.get(0);
      jdbcTemplate.update(
          "UPDATE app_user SET last_login_at = ?, wx_unionid = COALESCE(?, wx_unionid) WHERE id = ?",
          ts,
          union,
          id);
      return new UserUpsertResult(id, false);
    }
    String nickname = nicknameFor(openid);
    jdbcTemplate.update(
        "INSERT INTO app_user (nickname, wx_openid, wx_unionid, last_login_at) VALUES (?,?,?,?)",
        nickname,
        openid,
        union,
        ts);
    Long id = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    if (id == null || id == 0L) {
      throw new IllegalStateException("failed to obtain new user id");
    }
    return new UserUpsertResult(id, true);
  }

  private static String emptyToNull(String s) {
    return (s == null || s.isBlank()) ? null : s;
  }

  private static String nicknameFor(String openid) {
    String tail = openid.length() > 6 ? openid.substring(openid.length() - 6) : openid;
    return "用户" + tail;
  }
}
