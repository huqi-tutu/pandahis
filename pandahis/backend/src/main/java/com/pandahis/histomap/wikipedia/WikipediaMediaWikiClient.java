package com.pandahis.histomap.wikipedia;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.config.HistomapProperties;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/**
 * 中文维基 MediaWiki API 客户端（对齐 historiography wikipedia_client.py 的只读检索思路）。
 * 产品侧用整页 parse 纯文本，避免按章节串行请求。
 */
@Component
public class WikipediaMediaWikiClient implements WikipediaClient {
  private static final Pattern EDIT_MARK = Pattern.compile("\\[编辑[^\\]]*\\]");
  private static final Pattern HTML_TAG = Pattern.compile("(?is)<[^>]+>");
  private static final Pattern SCRIPT_STYLE =
      Pattern.compile("(?is)<(script|style)[^>]*>.*?</\\1>");
  private static final Pattern REF_SUP =
      Pattern.compile("(?is)<sup[^>]*>.*?</sup>");

  private final HistomapProperties props;
  private final ObjectMapper objectMapper;
  private final HttpClient httpClient;

  public WikipediaMediaWikiClient(HistomapProperties props, ObjectMapper objectMapper) {
    this.props = props;
    this.objectMapper = objectMapper;
    this.httpClient =
        HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(Math.max(3, props.getWikipedia().getConnectTimeoutSeconds())))
            .build();
  }

  @Override
  public Optional<WikipediaArticle> fetchArticle(String query) {
    String q = query == null ? "" : query.trim();
    if (q.isEmpty()) {
      return Optional.empty();
    }

    List<String> candidates = searchTitles(q, 5);
    String title = resolveTitle(q, candidates);
    if (title == null || title.isBlank()) {
      return Optional.empty();
    }

    ResolvedPage resolved = resolvePage(title);
    if (resolved == null) {
      return Optional.empty();
    }

    String plain = fetchPagePlainText(resolved.resolvedTitle());
    if (plain.isBlank()) {
      plain = resolved.extract();
    }
    int maxChars = Math.max(2000, props.getWikipedia().getMaxExtractChars());
    if (plain.length() > maxChars) {
      plain = plain.substring(0, maxChars);
    }

    List<String> paragraphs = WikipediaTextCleaner.toParagraphs(plain);
    if (paragraphs.isEmpty()) {
      return Optional.empty();
    }
    return Optional.of(new WikipediaArticle(resolved.resolvedTitle(), paragraphs));
  }

  private String resolveTitle(String query, List<String> candidates) {
    for (String c : candidates) {
      if (query.equals(c)) {
        return c;
      }
    }
    if (!candidates.isEmpty()) {
      return candidates.get(0);
    }
    return query;
  }

  private List<String> searchTitles(String query, int limit) {
    JsonNode data =
        request(
            "action=opensearch&format=json&namespace=0&limit="
                + limit
                + "&search="
                + encode(query));
    if (data == null || !data.isArray() || data.size() < 2 || !data.get(1).isArray()) {
      return List.of();
    }
    List<String> titles = new ArrayList<>();
    for (JsonNode n : data.get(1)) {
      String t = n.asText("").trim();
      if (!t.isEmpty()) {
        titles.add(t);
      }
    }
    return titles;
  }

  private ResolvedPage resolvePage(String title) {
    JsonNode queryData =
        request(
            "action=query&format=json&redirects=1"
                + "&prop=extracts|info"
                + "&explaintext=1&exintro=0"
                + "&titles="
                + encode(title));
    if (queryData == null) {
      return null;
    }
    JsonNode pages = queryData.path("query").path("pages");
    if (!pages.isObject()) {
      return null;
    }
    Iterator<String> fieldNames = pages.fieldNames();
    if (!fieldNames.hasNext()) {
      return null;
    }
    JsonNode page = pages.get(fieldNames.next());
    if (page == null || page.has("missing") || page.path("ns").asInt(0) != 0) {
      return null;
    }
    String resolved = page.path("title").asText(title).trim();
    String extract = page.path("extract").asText("").trim();
    return new ResolvedPage(resolved, extract);
  }

  private String fetchPagePlainText(String title) {
    JsonNode parseData =
        request("action=parse&format=json&prop=text&disableeditsection=1&page=" + encode(title));
    if (parseData == null) {
      return "";
    }
    JsonNode textNode = parseData.path("parse").path("text");
    String html = textNode.isObject() ? textNode.path("*").asText("") : textNode.asText("");
    return htmlToPlain(html);
  }

  private static String htmlToPlain(String html) {
    if (html == null || html.isBlank()) {
      return "";
    }
    String text = SCRIPT_STYLE.matcher(html).replaceAll("");
    text = REF_SUP.matcher(text).replaceAll("");
    text = text.replaceAll("(?i)<br\\s*/?>", "\n");
    text = text.replaceAll("(?i)</p\\s*>", "\n\n");
    text = text.replaceAll("(?i)</(div|li|tr|h[1-6])\\s*>", "\n\n");
    text = HTML_TAG.matcher(text).replaceAll("");
    text = EDIT_MARK.matcher(text).replaceAll("");
    text = text.replace('\u00a0', ' ');
    text = text.replace("&#91;", "").replace("&#93;", "");
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">");
    text = text.replace("&quot;", "\"");
    return text.trim();
  }

  private JsonNode request(String queryString) {
    HistomapProperties.Wikipedia cfg = props.getWikipedia();
    String base = cfg.getApiBase().trim();
    if (base.endsWith("?")) {
      base = base.substring(0, base.length() - 1);
    }
    URI uri = URI.create(base + "?" + queryString);
    HttpRequest.Builder builder =
        HttpRequest.newBuilder()
            .uri(uri)
            .timeout(Duration.ofSeconds(Math.max(5, cfg.getRequestTimeoutSeconds())))
            .header("User-Agent", cfg.getUserAgent())
            .GET();
    String token = cfg.getAccessToken();
    if (token != null && !token.isBlank()) {
      builder.header("Authorization", "Bearer " + token.trim());
    }

    try {
      HttpResponse<String> response =
          httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
      if (response.statusCode() != 200) {
        throw new RuntimeException("维基 API HTTP " + response.statusCode());
      }
      JsonNode data = objectMapper.readTree(response.body());
      if (data != null && data.has("error")) {
        throw new RuntimeException(
            "维基 API 错误: "
                + data.path("error").path("code").asText()
                + " "
                + data.path("error").path("info").asText());
      }
      return data;
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new RuntimeException("维基 API 请求被中断", e);
    } catch (IOException e) {
      throw new RuntimeException("维基 API 网络错误", e);
    }
  }

  private static String encode(String value) {
    return URLEncoder.encode(value, StandardCharsets.UTF_8);
  }

  private record ResolvedPage(String resolvedTitle, String extract) {}
}
