## 文档驱动实现（断点续跑指南）

本仓库按“前后端分离 + 文档单一事实源”组织，用来实现《系统设计文档-历史图谱-v2.md》对应的 v1 项目。

### 目录约定

- `backend/`：Spring Boot 后端（单体，但按 bounded context 分包隔离）
- `miniapp/`：uni-app（Vue）小程序端（面向微信小程序）
- `docs/`：实现契约与运行手册（上下文锚点）
  - `docs/spec/`：API 契约（OpenAPI）与 DTO schemas（JSON Schema）
  - `docs/adr/`：关键决策记录（ADR）
  - `docs/runbooks/`：联调/回归/支付回调等操作手册
- `plans/`：**可断点续跑**的阶段包（Step Pack）

### 断点续跑规则（上下文压缩后仍可执行）

每个阶段在 `plans/` 里都有一个 step 文档，固定包含：

- **Context brief**：本阶段做什么、不做什么、依赖哪些已存在产物（路径级）。
- **Deliverables**：必须新增/修改的文件清单（路径级）。
- **Verification**：可重复的验证命令/操作。
- **Exit criteria**：可验收的完成定义（DoD）。

当聊天上下文被压缩或换新会话时，执行者只需要：

1. 打开 `plans/`，选择下一个未完成 step。
2. 以 `docs/spec/openapi.yaml` 与 `docs/spec/dtos/*.schema.json` 为单一事实源继续实现。
3. 完成该 step 的 Deliverables，并按 Verification/Exit criteria 验收后再进入下一步。

