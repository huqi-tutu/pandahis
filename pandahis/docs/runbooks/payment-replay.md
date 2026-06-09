## 支付回调重放与幂等验证（Payment Replay）

### 目标

验证回调处理满足：

- **幂等**：同一 `wxTransactionId` 重放不会重复把订单从 created 置 paid，也不会重复延长会员。
- **状态机**：仅允许 `created -> paid`；其他状态收到回调应直接返回 OK 并记录日志（v1 先不做告警系统）。

### v1 说明（当前实现）

本仓库 v1 的 `/payments/wechat/notify` 是联调用的抽象结构（不绑定微信字段版本），真实微信验签接入将在后续迭代补齐。\n+当前幂等键：`payment_callback_log.wx_transaction_id`（唯一约束）。\n+
### 操作步骤（建议用 Postman 或 curl）

1. 登录态创建订单：\n+   - `POST /api/v1/orders` body: `{\"planId\":\"year\"}`，带 `Authorization: Bearer dev`\n+   - 记下返回的 `orderId`\n+2. 第一次回调：\n+   - `POST /api/v1/payments/wechat/notify` body: `{\"orderId\":<orderId>,\"wxTransactionId\":\"wx-replay-1\",\"paidAt\":\"2026-04-27T00:00:00Z\"}`\n+3. 重放回调（重复 10 次）：\n+   - 使用相同 body 重复请求\n+4. 验证：\n+   - `GET /api/v1/orders/{orderId}`：状态应为 `paid`\n+   - `GET /api/v1/membership`：状态应为 `ACTIVE`\n+\n*** End Patch"}]}  فعل to=functions.ApplyPatch in commentary  彩神争霸提现assistant to=functions.ApplyPatch is interrupted by the user. command: *** Begin Patch
