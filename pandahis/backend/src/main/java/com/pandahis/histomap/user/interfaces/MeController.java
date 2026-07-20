package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.HomeMatrixStateDTO;
import com.pandahis.histomap.user.interfaces.dto.MeDTO;
import com.pandahis.histomap.user.interfaces.service.AvatarStorageService;
import com.pandahis.histomap.user.interfaces.service.HomeMatrixStateService;
import com.pandahis.histomap.user.interfaces.service.HomeMatrixStateService.SaveHomeMatrixStateCommand;
import com.pandahis.histomap.user.interfaces.service.MeService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping
public class MeController {
  private final MeService meService;
  private final HomeMatrixStateService homeMatrixStateService;
  private final AvatarStorageService avatarStorageService;

  public MeController(
      MeService meService,
      HomeMatrixStateService homeMatrixStateService,
      AvatarStorageService avatarStorageService
  ) {
    this.meService = meService;
    this.homeMatrixStateService = homeMatrixStateService;
    this.avatarStorageService = avatarStorageService;
  }

  @RequireAuth
  @GetMapping("/me")
  public ApiResponse<MeDTO> me() {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), meService.load(userId));
  }

  @RequireAuth
  @PatchMapping("/me/profile")
  public ApiResponse<MeDTO> updateProfile(@Valid @RequestBody UpdateProfileRequest body) {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), meService.updateNickname(userId, body.nickname()));
  }

  @RequireAuth
  @PostMapping(value = "/me/avatar", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
  public ApiResponse<MeDTO> uploadAvatar(
      @RequestParam("file") MultipartFile file,
      HttpServletRequest request
  ) {
    Long userId = UserContextHolder.get().userId();
    String previousUrl = meService.currentAvatarUrl(userId);
    AvatarStorageService.StoredAvatar stored = avatarStorageService.store(userId, file);
    String publicUrl = buildAvatarPublicUrl(request, stored.filename());
    MeDTO me = meService.updateAvatarUrl(userId, publicUrl);
    avatarStorageService.deleteManagedFileFromUrl(previousUrl);
    return ApiResponse.ok(RequestIdHolder.get(), me);
  }

  /** 公开读取头像文件（文件名含随机 UUID，无需鉴权以便 image 组件直接加载）。 */
  @GetMapping("/me/avatar/files/{filename}")
  public ResponseEntity<Resource> avatarFile(@PathVariable("filename") String filename) {
    Resource resource = avatarStorageService.load(filename);
    String contentType = avatarStorageService.contentTypeForFilename(filename);
    return ResponseEntity.ok()
        .contentType(MediaType.parseMediaType(contentType))
        .cacheControl(CacheControl.maxAge(30, TimeUnit.DAYS).cachePublic())
        .body(resource);
  }

  @RequireAuth
  @GetMapping("/me/home-matrix-state")
  public ApiResponse<HomeMatrixStateDTO> homeMatrixState() {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(RequestIdHolder.get(), homeMatrixStateService.load(userId));
  }

  @RequireAuth
  @PutMapping("/me/home-matrix-state")
  public ApiResponse<HomeMatrixStateDTO> saveHomeMatrixState(
      @Valid @RequestBody SaveHomeMatrixStateRequest body
  ) {
    Long userId = UserContextHolder.get().userId();
    return ApiResponse.ok(
        RequestIdHolder.get(),
        homeMatrixStateService.save(
            userId,
            new SaveHomeMatrixStateCommand(
                body.civilizationCode(),
                body.lastDynastyKey(),
                body.collapsedDynastyKeys(),
                body.lastScrollTopPx()
            )
        )
    );
  }

  private static String buildAvatarPublicUrl(HttpServletRequest request, String filename) {
    String configured = System.getenv("HISTOMAP_AVATAR_PUBLIC_BASE");
    if (configured != null && !configured.isBlank()) {
      return configured.replaceAll("/$", "") + "/me/avatar/files/" + filename;
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
    return scheme + "://" + host + contextPath + "/me/avatar/files/" + filename;
  }

  public record UpdateProfileRequest(@NotBlank @Size(min = 1, max = 32) String nickname) {}

  public record SaveHomeMatrixStateRequest(
      @Size(max = 16) String civilizationCode,
      @Size(max = 64) String lastDynastyKey,
      List<@Size(max = 64) String> collapsedDynastyKeys,
      @PositiveOrZero Integer lastScrollTopPx
  ) {}
}
