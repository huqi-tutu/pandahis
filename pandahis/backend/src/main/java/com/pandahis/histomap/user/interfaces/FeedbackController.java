package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.FeedbackDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.FeedbackImageUploadDTO;
import com.pandahis.histomap.user.interfaces.dto.FeedbackSubmitRequest;
import com.pandahis.histomap.user.interfaces.service.FeedbackImageStorageService;
import com.pandahis.histomap.user.interfaces.service.FeedbackService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.concurrent.TimeUnit;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
public class FeedbackController {
  private final FeedbackService feedbackService;
  private final FeedbackImageStorageService imageStorageService;

  public FeedbackController(
      FeedbackService feedbackService, FeedbackImageStorageService imageStorageService) {
    this.feedbackService = feedbackService;
    this.imageStorageService = imageStorageService;
  }

  @RequireAuth
  @PostMapping(value = "/feedback/images", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
  public ApiResponse<FeedbackImageUploadDTO> uploadImage(
      @RequestParam("file") MultipartFile file, HttpServletRequest request) {
    long userId = UserContextHolder.get().userId();
    FeedbackImageStorageService.StoredImage stored = imageStorageService.store(userId, file);
    String url = buildPublicUrl(request, stored.filename());
    return ApiResponse.ok(RequestIdHolder.get(), new FeedbackImageUploadDTO(url));
  }

  @GetMapping("/feedback/images/files/{filename}")
  public ResponseEntity<Resource> imageFile(@PathVariable("filename") String filename) {
    Resource resource = imageStorageService.load(filename);
    String contentType = imageStorageService.contentTypeForFilename(filename);
    return ResponseEntity.ok()
        .contentType(MediaType.parseMediaType(contentType))
        .cacheControl(CacheControl.maxAge(30, TimeUnit.DAYS).cachePublic())
        .body(resource);
  }

  @RequireAuth
  @PostMapping("/feedback")
  public ApiResponse<FeedbackDetailDTO> submit(@Valid @RequestBody FeedbackSubmitRequest req) {
    return ApiResponse.ok(
        RequestIdHolder.get(), feedbackService.submit(UserContextHolder.get().userId(), req));
  }

  @RequireAuth
  @GetMapping("/feedback/{id}")
  public ApiResponse<FeedbackDetailDTO> detail(@PathVariable long id) {
    return ApiResponse.ok(
        RequestIdHolder.get(), feedbackService.detail(UserContextHolder.get().userId(), id));
  }

  private static String buildPublicUrl(HttpServletRequest request, String filename) {
    String configured = System.getenv("HISTOMAP_FEEDBACK_PUBLIC_BASE");
    if (configured != null && !configured.isBlank()) {
      return configured.replaceAll("/$", "") + "/feedback/images/files/" + filename;
    }
    String avatarBase = System.getenv("HISTOMAP_AVATAR_PUBLIC_BASE");
    if (avatarBase != null && !avatarBase.isBlank()) {
      // 与头像共用 API 根时，直接拼反馈路径
      String root = avatarBase.replaceAll("/$", "").replaceAll("/me/avatar/files/?$", "");
      return root + "/feedback/images/files/" + filename;
    }
    String scheme = request.getHeader("X-Forwarded-Proto");
    if (scheme == null || scheme.isBlank()) {
      scheme = request.getScheme();
    }
    String host = request.getHeader("X-Forwarded-Host");
    if (host == null || host.isBlank()) {
      host = request.getHeader("Host");
    }
    if (host == null || host.isBlank()) {
      host = request.getServerName() + (request.getServerPort() > 0 ? ":" + request.getServerPort() : "");
    }
    String contextPath = request.getContextPath() == null ? "" : request.getContextPath();
    return scheme + "://" + host + contextPath + "/feedback/images/files/" + filename;
  }
}
