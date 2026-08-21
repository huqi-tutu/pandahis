package com.pandahis.histomap.narration.service;

import com.pandahis.histomap.common.api.ApiException;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * 服务端 TTS（Edge Read Aloud）。
 * 单次 Edge 上限约 480 字；对更长文本按句切分后合成并拼接为连续 MP3，
 * 供小程序用更少换源次数实现接近无感续播。
 */
@Service
public class EdgeNarrationService {
  private static final String TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4";
  private static final String VOICE = "zh-CN-XiaoxiaoNeural";
  /** 单次 Edge 请求字数上限 */
  private static final int EDGE_MAX_CHARS = 480;
  /** 接口允许的拼接总字数（与 DTO @Size 对齐） */
  private static final int JOIN_MAX_CHARS = 2000;

  private final HttpClient httpClient =
      HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(12)).build();

  public byte[] synthesizeMp3(String text) {
    String content = normalize(text);
    if (content.isEmpty()) {
      throw ApiException.invalidArgument("朗读文本为空");
    }
    if (content.length() > JOIN_MAX_CHARS) {
      content = content.substring(0, JOIN_MAX_CHARS);
    }

    List<String> parts = splitForEdge(content, EDGE_MAX_CHARS);
    if (parts.isEmpty()) {
      throw ApiException.invalidArgument("朗读文本为空");
    }
    if (parts.size() == 1) {
      return synthesizeOne(parts.get(0));
    }

    // 保序并行合成，缩短长文首包等待
    @SuppressWarnings("unchecked")
    java.util.concurrent.CompletableFuture<byte[]>[] futures =
        parts.stream()
            .map(
                part ->
                    java.util.concurrent.CompletableFuture.supplyAsync(() -> synthesizeOne(part)))
            .toArray(java.util.concurrent.CompletableFuture[]::new);

    ByteArrayOutputStream out = new ByteArrayOutputStream(parts.size() * 32_000);
    try {
      for (java.util.concurrent.CompletableFuture<byte[]> future : futures) {
        byte[] mp3 = future.join();
        out.write(mp3);
      }
    } catch (ApiException e) {
      throw e;
    } catch (Exception e) {
      Throwable cause = e.getCause() != null ? e.getCause() : e;
      if (cause instanceof ApiException apiEx) {
        throw apiEx;
      }
      throw ApiException.internalError("语音拼接失败");
    }
    byte[] joined = out.toByteArray();
    if (joined.length < 128) {
      throw ApiException.internalError("语音合成结果无效");
    }
    return joined;
  }

  private byte[] synthesizeOne(String content) {
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

  /** 按句读切分，单段不超过 maxLen；超长句硬切。 */
  static List<String> splitForEdge(String text, int maxLen) {
    List<String> sentences = new ArrayList<>();
    StringBuilder seg = new StringBuilder();
    for (int i = 0; i < text.length(); i++) {
      char ch = text.charAt(i);
      seg.append(ch);
      if (ch == '。' || ch == '！' || ch == '？' || ch == '；' || ch == '\n') {
        String t = seg.toString().trim();
        if (!t.isEmpty()) sentences.add(t);
        seg.setLength(0);
      }
    }
    String tail = seg.toString().trim();
    if (!tail.isEmpty()) sentences.add(tail);

    List<String> out = new ArrayList<>();
    StringBuilder buf = new StringBuilder();
    for (String part : sentences) {
      if (part.length() > maxLen) {
        flushBuf(buf, out);
        for (int i = 0; i < part.length(); i += maxLen) {
          out.add(part.substring(i, Math.min(part.length(), i + maxLen)));
        }
        continue;
      }
      if (buf.length() + part.length() <= maxLen) {
        buf.append(part);
      } else {
        flushBuf(buf, out);
        buf.append(part);
      }
    }
    flushBuf(buf, out);
    return out;
  }

  private static void flushBuf(StringBuilder buf, List<String> out) {
    if (buf.length() == 0) return;
    String t = buf.toString().trim();
    if (!t.isEmpty()) out.add(t);
    buf.setLength(0);
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
