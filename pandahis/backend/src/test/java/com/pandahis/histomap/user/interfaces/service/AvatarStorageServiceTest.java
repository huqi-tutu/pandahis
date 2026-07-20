package com.pandahis.histomap.user.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.pandahis.histomap.common.api.ApiException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.Resource;
import org.springframework.mock.web.MockMultipartFile;

class AvatarStorageServiceTest {
  @TempDir
  Path tempDir;

  private static final byte[] PNG_BYTES = new byte[] {
      (byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
      0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52
  };

  @Test
  void storeAndLoadRoundTrip() throws Exception {
    AvatarStorageService service = new AvatarStorageService(tempDir.toString());
    MockMultipartFile file =
        new MockMultipartFile("file", "avatar.png", "image/png", PNG_BYTES);

    AvatarStorageService.StoredAvatar stored = service.store(42L, file);
    assertTrue(stored.filename().startsWith("42_"));
    assertTrue(stored.filename().endsWith(".png"));
    assertEquals("image/png", stored.contentType());

    Resource resource = service.load(stored.filename());
    assertTrue(resource.exists());
    assertEquals(PNG_BYTES.length, Files.readAllBytes(resource.getFile().toPath()).length);
  }

  @Test
  void rejectsNonImageContent() {
    AvatarStorageService service = new AvatarStorageService(tempDir.toString());
    MockMultipartFile file =
        new MockMultipartFile("file", "a.png", "image/png", "not-an-image".getBytes());
    assertThrows(ApiException.class, () -> service.store(1L, file));
  }

  @Test
  void rejectsOversizedFile() {
    AvatarStorageService service = new AvatarStorageService(tempDir.toString());
    byte[] big = new byte[2 * 1024 * 1024 + 1];
    big[0] = (byte) 0xFF;
    big[1] = (byte) 0xD8;
    big[2] = (byte) 0xFF;
    MockMultipartFile file = new MockMultipartFile("file", "a.jpg", "image/jpeg", big);
    assertThrows(ApiException.class, () -> service.store(1L, file));
  }

  @Test
  void rejectsPathTraversalFilename() {
    AvatarStorageService service = new AvatarStorageService(tempDir.toString());
    assertThrows(ApiException.class, () -> service.load("../secret.jpg"));
  }
}
