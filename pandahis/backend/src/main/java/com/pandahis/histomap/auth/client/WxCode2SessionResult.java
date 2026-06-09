package com.pandahis.histomap.auth.client;

public record WxCode2SessionResult(String openid, String sessionKey, String unionid) {}
