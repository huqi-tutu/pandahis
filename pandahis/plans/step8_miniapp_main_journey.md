## Step8：小程序主链路（首页→单元→盒子）

### Context brief

本阶段把 SCREEN01/02/03-06 的主链路连起来：首页加载 grid → 进入单元详情 → 点击盒子进入盒子详情，并完成基础的请求/跳转/空态。

### Deliverables

- `miniapp/src/pages/home/index.vue`：对接 `GET /home/grid` 并能跳转单元详情
- `miniapp/src/pages/unit-detail/index.vue`：对接 `GET /units/{id}` 与 `/matrix` 并能跳转盒子详情
- `miniapp/src/pages/box-detail/index.vue`：对接 `GET /boxes/{id}` 与 `/detail`

### Verification

- 从首页点击卡片可进入单元页；从单元页点击 item 可进入盒子页
- 所有请求走 `src/utils/api.ts`，401 时可跳登录并回跳

### Exit criteria

- Journey A 的基础读链路页面可跑通（后续在 Step8/11 再补虚拟化、tabs 懒加载、收藏足迹联动等细节）。

