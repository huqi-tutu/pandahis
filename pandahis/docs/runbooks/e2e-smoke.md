## 冒烟联调手册（E2E Smoke）

> 目标：把 `docs/runbooks/integration-checklist.md` 变成“一次可执行的跑通步骤”。  
> 注意：本仓库后端默认连接 MySQL（`application.yaml`），`spring.sql.init.mode: never`；库表与种子数据请在库内按 `docs/DEPLOY.md` 初始化。

### 0. 启动后端（本地）

- **方式 A（推荐）**：使用 Maven Wrapper（不要求本机安装 Maven）

```bash
cd backend
./mvnw spring-boot:run
```

Windows PowerShell：

```powershell
cd backend
.\mvnw.cmd spring-boot:run
```

- **方式 B**：用 IDE 直接运行主类 `com.pandahis.histomap.HistomapApiApplication`
### 1. 读接口冒烟（可用 curl 或 Postman）

- **GET `/api/v1/health`**：预期 `code=OK`，`data.status=ok`
- **GET `/api/v1/home/grid`**：预期有 `timeAxis/civilizations/cells`
- **GET `/api/v1/units/huaxia_song_shenzong`**：预期 `unit.name=宋神宗`
- **GET `/api/v1/units/huaxia_song_shenzong/matrix`**：预期 items 至少含 `box_wutai_1079`
- **GET `/api/v1/boxes/box_wutai_1079`**：预期有 `tabSummary` 与 `access.tabs.*`
- **GET `/api/v1/boxes/box_wutai_1079/detail`**：预期返回 `detailMd`
### 2. 登录态冒烟（用 Bearer token 占位）

> v1 骨架中：只要带 `Authorization: Bearer <anything>` 即视为已登录（用于联调）。

- **GET `/api/v1/me`**（需 Authorization）：预期 `nickname=测试用户`
- **POST `/api/v1/favorites/boxes/box_wutai_1079`**（需 Authorization）：预期 OK（幂等）
- **POST `/api/v1/footprints/boxes/box_wutai_1079/view`**（需 Authorization）：预期 OK（upsert 幂等）
### 3. 搜索冒烟

- **GET `/api/v1/search/suggest`**：预期 hotKeywords 包含 “乌台诗案”
- **GET `/api/v1/search?q=乌台`**：预期 items 至少含 type=box 的结果
### 4. 会员/支付冒烟（mock notify）

- **GET `/api/v1/membership/plans`**：预期含 month/year，year 为默认
- **POST `/api/v1/orders`**（需 Authorization）：body `{\"planId\":\"year\"}`，预期返回 orderId 与 payParams
- **POST `/api/v1/payments/wechat/notify`**：body `{\"orderId\":<orderId>,\"wxTransactionId\":\"wx-mock-1\",\"paidAt\":\"2026-04-27T00:00:00Z\"}`，预期 OK（幂等）
- **GET `/api/v1/membership`**（需 Authorization）：预期 ACTIVE
