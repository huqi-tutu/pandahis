package com.pandahis.histomap.user.interfaces.dto;

import jakarta.validation.constraints.Size;

public record NoteUpdateRequest(@Size(max = 2000) String noteText) {}
