package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

@Service
public class FeedbackImageStorageService {
  private static final Set<String> ALLOWED_EXT = Set.of("jpg", "jpeg", "png", "webp");
  private static final long MAX_BYTES = 1024L * 1024L;
  /** 每人每天最多上传反馈图片次数（含未最终提交的） */
  public static final int MAX_DAILY_UPLOADS = 15;
  private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

  private final Path storageDir;

  public FeedbackImageStorageService(
      @Value("${histomap.feedback.storage-dir:./data/feedback}") String storageDir
  ) {
    this.storageDir = Path.of(storageDir).toAbsolutePath().normalize();
  }

  public StoredImage store(long userId, MultipartFile file) {
    enforceDailyUploadLimit(userId);
    if (file == null || file.isEmpty()) {
      throw ApiException.invalidArgument("请选择图片");
    }
    if (file.getSize() > MAX_BYTES) {
      throw ApiException.invalidArgument("图片大小不能超过 1MB");
    }

    String ext = resolveExtension(file);
    if (!ALLOWED_EXT.contains(ext)) {
      throw ApiException.invalidArgument("仅支持 jpg / png / webp 格式");
    }
    if ("jpeg".equals(ext)) {
      ext = "jpg";
    }

    ensureDir();
    String filename = userId + "_" + UUID.randomUUID().toString().replace("-", "") + "." + ext;
    Path target = storageDir.resolve(filename).normalize();
    if (!target.startsWith(storageDir)) {
      throw ApiException.invalidArgument("非法文件名");
    }

    try {
      byte[] bytes = file.getBytes();
      if (bytes.length == 0 || bytes.length > MAX_BYTES) {
        throw ApiException.invalidArgument("图片大小不能超过 1MB");
      }
      if (!looksLikeImage(bytes, ext)) {
        throw ApiException.invalidArgument("文件内容不是有效图片");
      }
      Files.write(target, bytes);
    } catch (ApiException e) {
      throw e;
    } catch (IOException e) {
      throw ApiException.internalError("图片保存失败");
    }
    return new StoredImage(filename, contentTypeFor(ext));
  }

  public void enforceDailyUploadLimit(long userId) {
    long count = countUploadsToday(userId);
    if (count >= MAX_DAILY_UPLOADS) {
      throw ApiException.rateLimited("今日反馈图片上传次数已达上限（" + MAX_DAILY_UPLOADS + "次）");
    }
  }

  public boolean existsOwned(long userId, String filename) {
    String safe;
    try {
      safe = sanitizeFilename(filename);
    } catch (ApiException e) {
      return false;
    }
    if (!safe.startsWith(userId + "_")) {
      return false;
    }
    Path path = storageDir.resolve(safe).normalize();
    return path.startsWith(storageDir) && Files.isRegularFile(path);
  }

  public Resource load(String filename) {
    String safe = sanitizeFilename(filename);
    Path path = storageDir.resolve(safe).normalize();
    if (!path.startsWith(storageDir) || !Files.isRegularFile(path)) {
      throw ApiException.notFound("图片不存在");
    }
    return new FileSystemResource(path);
  }

  public String contentTypeForFilename(String filename) {
    String ext = extensionOf(sanitizeFilename(filename));
    return contentTypeFor(ext);
  }

  long countUploadsToday(long userId) {
    ensureDir();
    String prefix = userId + "_";
    LocalDate today = LocalDate.now(ZONE);
    try (Stream<Path> stream = Files.list(storageDir)) {
      return stream
          .filter(Files::isRegularFile)
          .filter(p -> p.getFileName().toString().startsWith(prefix))
          .filter(p -> isCreatedOn(p, today))
          .count();
    } catch (IOException e) {
      throw ApiException.internalError("反馈图片目录不可用");
    }
  }

  private static boolean isCreatedOn(Path path, LocalDate day) {
    try {
      BasicFileAttributes attrs = Files.readAttributes(path, BasicFileAttributes.class);
      Instant created = attrs.creationTime().toInstant();
      // 部分文件系统 creationTime 不可用时回退 lastModified
      if (created.getEpochSecond() <= 0) {
        created = attrs.lastModifiedTime().toInstant();
      }
      return created.atZone(ZONE).toLocalDate().equals(day);
    } catch (IOException e) {
      return false;
    }
  }

  private void ensureDir() {
    try {
      Files.createDirectories(storageDir);
    } catch (IOException e) {
      throw ApiException.internalError("反馈图片目录不可用");
    }
  }

  private static String resolveExtension(MultipartFile file) {
    String original = file.getOriginalFilename();
    String fromName = extensionOf(original == null ? "" : original);
    if (!fromName.isBlank() && ALLOWED_EXT.contains(fromName)) {
      return fromName;
    }
    String contentType = file.getContentType() == null ? "" : file.getContentType().toLowerCase(Locale.ROOT);
    return switch (contentType) {
      case "image/jpeg", "image/jpg" -> "jpg";
      case "image/png" -> "png";
      case "image/webp" -> "webp";
      default -> fromName;
    };
  }

  private static String extensionOf(String name) {
    int idx = name.lastIndexOf('.');
    if (idx < 0 || idx == name.length() - 1) return "";
    return name.substring(idx + 1).toLowerCase(Locale.ROOT);
  }

  static String sanitizeFilename(String filename) {
    if (filename == null || filename.isBlank()) {
      throw ApiException.invalidArgument("非法文件名");
    }
    String name = filename.trim();
    if (name.contains("..") || name.contains("/") || name.contains("\\")) {
      throw ApiException.invalidArgument("非法文件名");
    }
    if (!name.matches("^[0-9]+_[a-f0-9]{32}\\.(jpg|jpeg|png|webp)$")) {
      throw ApiException.invalidArgument("非法文件名");
    }
    return name;
  }

  private static String contentTypeFor(String ext) {
    return switch (ext) {
      case "png" -> "image/png";
      case "webp" -> "image/webp";
      default -> "image/jpeg";
    };
  }

  private static boolean looksLikeImage(byte[] header, String ext) {
    if (header == null || header.length < 3) return false;
    return switch (ext) {
      case "png" -> header.length >= 8
          && header[0] == (byte) 0x89
          && header[1] == 0x50
          && header[2] == 0x4E
          && header[3] == 0x47;
      case "jpg", "jpeg" -> header[0] == (byte) 0xFF && header[1] == (byte) 0xD8 && header[2] == (byte) 0xFF;
      case "webp" -> header.length >= 12
          && header[0] == 'R'
          && header[1] == 'I'
          && header[2] == 'F'
          && header[3] == 'F'
          && header[8] == 'W'
          && header[9] == 'E'
          && header[10] == 'B'
          && header[11] == 'P';
      default -> false;
    };
  }

  public record StoredImage(String filename, String contentType) {}
}
