package com.pandahis.histomap.membership.interfaces.dto;

import java.util.Map;

public record CreateOrderDTO(long orderId, String status, Map<String, Object> payParams) {}

