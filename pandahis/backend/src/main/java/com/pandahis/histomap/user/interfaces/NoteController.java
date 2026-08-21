package com.pandahis.histomap.user.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.user.interfaces.dto.NoteDetailDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteDynastyListDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteHighlightDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteListDTO;
import com.pandahis.histomap.user.interfaces.dto.NoteSubmitRequest;
import com.pandahis.histomap.user.interfaces.dto.NoteUpdateRequest;
import com.pandahis.histomap.user.interfaces.service.NoteService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class NoteController {
  private final NoteService noteService;

  public NoteController(NoteService noteService) {
    this.noteService = noteService;
  }

  @RequireAuth
  @PostMapping("/notes")
  public ApiResponse<NoteDetailDTO> create(@Valid @RequestBody NoteSubmitRequest req) {
    return ApiResponse.ok(
        RequestIdHolder.get(), noteService.create(UserContextHolder.get().userId(), req));
  }

  @RequireAuth
  @GetMapping("/notes/dynasties")
  public ApiResponse<NoteDynastyListDTO> dynasties() {
    return ApiResponse.ok(
        RequestIdHolder.get(), noteService.listDynasties(UserContextHolder.get().userId()));
  }

  @RequireAuth
  @GetMapping("/notes/highlights")
  public ApiResponse<List<NoteHighlightDTO>> highlights(
      @RequestParam @NotBlank @Size(max = 128) String boxId,
      @RequestParam @NotBlank @Size(max = 32) String sourceType,
      @RequestParam(required = false) Long sourceRefId) {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        noteService.listHighlights(UserContextHolder.get().userId(), boxId, sourceType, sourceRefId));
  }

  @RequireAuth
  @GetMapping("/notes")
  public ApiResponse<NoteListDTO> list(
      @RequestParam @NotBlank @Size(max = 128) String dynastyId,
      @RequestParam(defaultValue = "1") @Min(1) int page,
      @RequestParam(defaultValue = "20") @Min(1) @Max(50) int pageSize) {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        noteService.listByDynasty(UserContextHolder.get().userId(), dynastyId, page, pageSize));
  }

  @RequireAuth
  @GetMapping("/notes/{id}")
  public ApiResponse<NoteDetailDTO> detail(@PathVariable long id) {
    return ApiResponse.ok(
        RequestIdHolder.get(), noteService.detail(UserContextHolder.get().userId(), id));
  }

  @RequireAuth
  @PatchMapping("/notes/{id}")
  public ApiResponse<NoteDetailDTO> update(
      @PathVariable long id, @Valid @RequestBody NoteUpdateRequest req) {
    return ApiResponse.ok(
        RequestIdHolder.get(), noteService.update(UserContextHolder.get().userId(), id, req));
  }

  @RequireAuth
  @DeleteMapping("/notes/{id}")
  public ApiResponse<Map<String, Object>> delete(@PathVariable long id) {
    noteService.delete(UserContextHolder.get().userId(), id);
    return ApiResponse.ok(RequestIdHolder.get(), Map.of());
  }
}
