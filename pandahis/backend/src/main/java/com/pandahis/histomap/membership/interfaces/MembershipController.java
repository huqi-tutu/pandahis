package com.pandahis.histomap.membership.interfaces;

import com.pandahis.histomap.common.api.ApiResponse;
import com.pandahis.histomap.common.auth.RequireAuth;
import com.pandahis.histomap.common.auth.UserContextHolder;
import com.pandahis.histomap.common.web.RequestIdHolder;
import com.pandahis.histomap.membership.interfaces.dto.*;
import com.pandahis.histomap.membership.interfaces.service.MembershipAssistService;
import com.pandahis.histomap.membership.interfaces.service.MembershipService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping
public class MembershipController {
  private final MembershipService membershipService;
  private final MembershipAssistService membershipAssistService;

  public MembershipController(
      MembershipService membershipService,
      MembershipAssistService membershipAssistService
  ) {
    this.membershipService = membershipService;
    this.membershipAssistService = membershipAssistService;
  }

  @GetMapping("/membership/plans")
  public ApiResponse<MembershipPlansDTO> plans() {
    return ApiResponse.ok(RequestIdHolder.get(), membershipService.listPlans());
  }

  @RequireAuth
  @GetMapping("/membership")
  public ApiResponse<MembershipDTO> membership() {
    return ApiResponse.ok(RequestIdHolder.get(), membershipService.getMembership(UserContextHolder.get().userId()));
  }

  @RequireAuth
  @GetMapping("/membership/assist")
  public ApiResponse<MembershipAssistDTO> assist() {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        membershipAssistService.getAssist(UserContextHolder.get().userId())
    );
  }

  @RequireAuth
  @PostMapping("/membership/assist/claim")
  public ApiResponse<MembershipAssistDTO> claimAssist() {
    return ApiResponse.ok(
        RequestIdHolder.get(),
        membershipAssistService.claimReward(UserContextHolder.get().userId())
    );
  }

  @RequireAuth
  @PostMapping("/orders")
  public ApiResponse<CreateOrderDTO> createOrder(@RequestBody @Valid CreateOrderRequest req) {
    return ApiResponse.ok(RequestIdHolder.get(), membershipService.createOrder(UserContextHolder.get().userId(), req.planId()));
  }

  @RequireAuth
  @GetMapping("/orders/{orderId}")
  public ApiResponse<OrderDTO> getOrder(@PathVariable long orderId) {
    return ApiResponse.ok(RequestIdHolder.get(), membershipService.getOrder(UserContextHolder.get().userId(), orderId));
  }

  @PostMapping("/payments/wechat/notify")
  public ApiResponse<java.util.Map<String, Object>> notify(@RequestBody @Valid WechatNotifyRequest req) {
    membershipService.handleNotify(req);
    return ApiResponse.ok(RequestIdHolder.get(), java.util.Map.of());
  }

  public record CreateOrderRequest(@NotBlank @Size(max = 32) String planId) {}

  public record WechatNotifyRequest(long orderId, @NotBlank @Size(max = 128) String wxTransactionId, @NotBlank String paidAt) {}
}

