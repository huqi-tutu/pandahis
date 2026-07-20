package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

@Service
public class AvatarStorageService {
  private static final Set<String> ALLOWED_EXT = Set.of("jpg", "jpeg", "png", "webp");
  private static final long MAX_BYTES = 2L * 1024 * 1024;

  private final Path storageDir;

  public AvatarStorageService(
      @Value("${histomap.avatar.storage-dir:./data/avatars}") String storageDir
  ) {
    this.storageDir = Path.of(storageDir).toAbsolutePath().normalize();
  }

  public StoredAvatar store(long userId, MultipartFile file) {
    if (file == null || file.isEmpty()) {
      throw ApiException.invalidArgument("请选择头像图片");
    }
    if (file.getSize() > MAX_BYTES) {
      throw ApiException.invalidArgument("头像大小不能超过 2MB");
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
        throw ApiException.invalidArgument("头像大小不能超过 2MB");
      }
      if (!looksLikeImage(bytes, ext)) {
        throw ApiException.invalidArgument("文件内容不是有效图片");
      }
      Files.write(target, bytes);
    } catch (ApiException e) {
      throw e;
    } catch (IOException e) {
      throw ApiException.internalError("头像保存失败");
    }
    return new StoredAvatar(filename, contentTypeFor(ext));
  }

  public Resource load(String filename) {
    String safe = sanitizeFilename(filename);
    Path path = storageDir.resolve(safe).normalize();
    if (!path.startsWith(storageDir) || !Files.isRegularFile(path)) {
      throw ApiException.notFound("头像不存在");
    }
    return new FileSystemResource(path);
  }

  /** 删除本服务托管的旧头像；非托管 URL 或非法文件名则忽略。 */
  public void deleteManagedFileFromUrl(String avatarUrl) {
    if (avatarUrl == null || avatarUrl.isBlank()) return;
    int idx = avatarUrl.lastIndexOf("/me/avatar/files/");
    if (idx < 0) return;
    String filename = avatarUrl.substring(idx + "/me/avatar/files/".length());
    int q = filename.indexOf('?');
    if (q >= 0) filename = filename.substring(0, q);
    try {
      String safe = sanitizeFilename(filename);
      Path path = storageDir.resolve(safe).normalize();
      if (path.startsWith(storageDir)) {
        Files.deleteIfExists(path);
      }
    } catch (Exception ignored) {
      // 清理失败不影响主流程
    }
  }

  public String contentTypeForFilename(String filename) {
    String ext = extensionOf(sanitizeFilename(filename));
    return contentTypeFor(ext);
  }

  private void ensureDir() {
    try {
      Files.createDirectories(storageDir);
    } catch (IOException e) {
      throw ApiException.internalError("头像目录不可用");
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

  private static String sanitizeFilename(String filename) {
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

  public record StoredAvatar(String filename, String contentType) {}
}
