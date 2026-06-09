## Step4：内容图谱核心读链路（Home / Unit / Box）

### Context brief

本阶段实现 v1 主链路的“只读”接口：首页网格、单元 hero/matrix/civ-tabs、盒子 header/detail/graph/critiques/relics。

- **做**：接口返回形状对齐 `docs/spec/openapi.yaml`；实现重要规则（稀疏、裁剪、条数限制等）。
- **不做**：不实现用户写入（收藏/足迹）与支付（在 Step5/Step7）。

### Deliverables

- 后端接口：
  - `GET /home/grid`
  - `GET /units/{unitId}`
  - `GET /units/{unitId}/matrix`
  - `GET /units/{unitId}/civ-tabs`
  - `GET /boxes/{boxId}`
  - `GET /boxes/{boxId}/detail`
  - `GET /boxes/{boxId}/graph`
  - `GET /boxes/{boxId}/critiques`
  - `GET /boxes/{boxId}/relics`

### Verification

- 通过 `docs/runbooks/integration-checklist.md` 中 “SCREEN01/02/03-06” 的读接口项。

### Exit criteria

- 读链路接口稳定，后续前端 Step8 可以直接按契约接入。

