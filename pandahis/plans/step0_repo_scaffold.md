## Step0：仓库初始化与工程边界（Repo Scaffold）

### Context brief

本阶段只做“仓库结构与断点续跑锚点”落盘，确保后续任何实现都能基于仓库内文档继续推进。

- **做**：创建根目录拆分与文档锚点；写清楚断点续跑规则。
- **不做**：不引入具体业务代码；不实现接口；不引入支付/登录等外部依赖。

### Deliverables

- `backend/`（目录存在即可）
- `miniapp/`（目录存在即可）
- `docs/README.md`
- `plans/step0_repo_scaffold.md`

### Verification

- 目录存在：`backend/`、`miniapp/`、`docs/`、`plans/`
- `docs/README.md` 描述了断点续跑规则与单一事实源位置

### Exit criteria

- 仓库结构固定，后续所有 step 只引用这些固定路径。

