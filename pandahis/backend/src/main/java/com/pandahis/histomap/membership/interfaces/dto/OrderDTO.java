package com.pandahis.histomap.membership.interfaces.dto;

public record OrderDTO(long orderId, String status, int amountCent, String paidAt, String planId) {}

