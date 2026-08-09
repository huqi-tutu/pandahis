package com.pandahis.histomap.common.feature;

/** 小程序启动时拉取的功能开关（与 /home/grid 内 flags 字段一致） */
public record FeatureFlagsDTO(boolean civSwitchEnabled) {}
