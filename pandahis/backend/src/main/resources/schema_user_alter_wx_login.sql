-- 已有库升级：在微信小程序登录接入时执行一次（新库直接用 schema_user.sql 即可）
ALTER TABLE app_user
  ADD COLUMN wx_openid VARCHAR(64) NULL AFTER phone_e164,
  ADD COLUMN wx_unionid VARCHAR(64) NULL AFTER wx_openid,
  ADD COLUMN last_login_at TIMESTAMP NULL AFTER wx_unionid;

ALTER TABLE app_user
  ADD UNIQUE KEY uk_app_user_wx_openid (wx_openid),
  ADD UNIQUE KEY uk_app_user_wx_unionid (wx_unionid);
