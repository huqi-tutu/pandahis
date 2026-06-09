## Step1：接口契约与公共约定落盘（Contracts & Conventions）

### Context brief

本阶段的目标是把“接口形状 + 错误码 + DTO 结构”落盘为单一事实源，后端与前端实现都必须以此为准，避免口径漂移。

- **做**：OpenAPI、DTO JSON Schema、ADR、联调 checklist。
- **不做**：不实现任何业务代码、不引入数据库。

### Deliverables

- `docs/spec/openapi.yaml`
- `docs/spec/dtos/*.schema.json`
- `docs/adr/ADR-0001-repo-structure.md`
- `docs/runbooks/integration-checklist.md`

### Verification

- `docs/spec/openapi.yaml` 存在，且覆盖：home/unit/box/search/auth/me/favorites/footprints/membership/orders/payments
- `docs/spec/dtos/` 下每个 `$ref` 对应文件都存在
- `docs/runbooks/integration-checklist.md` 可按接口逐条勾选

### Exit criteria

- 任何实现变更必须“先改契约再改代码”（以契约为单一事实源）。

