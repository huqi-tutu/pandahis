package com.pandahis.histomap.narration.service;

import com.pandahis.histomap.common.api.ApiException;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * 服务端 TTS（Edge Read Aloud），供小程序在无法使用「微信同声传译」插件时朗读详情。
 */
@Service
public class EdgeNarrationService {
  private static final String TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4";
  private static final String VOICE = "zh-CN-XiaoxiaoNeural";
  private static final int MAX_CHARS = 480;

  private final HttpClient httpClient =
      HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(12)).build();

  public byte[] synthesizeMp3(String text) {
    String content = normalize(text);
    if (content.isEmpty()) {
      throw ApiException.invalidArgument("朗读文本为空");
    }
    if (content.length() > MAX_CHARS) {
      content = content.substring(0, MAX_CHARS);
    }

    String ssml =
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>"
            + "<voice name='"
            + VOICE
            + "'>"
            + escapeXml(content)
            + "</voice></speak>";

    URI uri =
        URI.create(
            "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken="
                + TRUSTED_CLIENT_TOKEN);

    HttpRequest request =
        HttpRequest.newBuilder()
            .uri(uri)
            .timeout(Duration.ofSeconds(25))
            .header("Content-Type", "application/ssml+xml")
            .header("X-Microsoft-OutputFormat", "audio-24khz-48kbitrate-mono-mp3")
            .header(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")
            .POST(HttpRequest.BodyPublishers.ofString(ssml, StandardCharsets.UTF_8))
            .build();

    try {
      HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
      if (response.statusCode() != 200) {
        throw ApiException.internalError("语音合成服务暂不可用（HTTP " + response.statusCode() + "）");
      }
      byte[] body = response.body();
      if (body == null || body.length < 128) {
        throw ApiException.internalError("语音合成结果无效");
      }
      return body;
    } catch (ApiException e) {
      throw e;
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw ApiException.internalError("语音合成被中断");
    } catch (IOException e) {
      throw ApiException.internalError("语音合成失败，请检查服务器网络");
    }
  }

  private static String normalize(String text) {
    if (text == null) return "";
    return text
        .replace("\r\n", "\n")
        .replaceAll("[#*_`>\\[\\]()]", "")
        .replaceAll("\\s+", " ")
        .trim();
  }

  private static String escapeXml(String s) {
    return s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;");
  }
}
