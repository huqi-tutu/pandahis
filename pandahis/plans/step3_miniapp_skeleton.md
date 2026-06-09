## Step3：uni-app 小程序骨架（路由/页面壳/请求层/登录回跳）

### Context brief

本阶段只保证小程序工程“可运行 + 路由齐全 + 请求层具备 token 注入与 401 回跳”，不做任何业务渲染逻辑（业务将在 Step8/9/10）。

- **做**：页面壳（11 屏）、tabbar、暗色主题、统一请求封装、登录回跳（redirect）。
- **不做**：不实现真实微信登录、不对接真实业务接口（仅保留调用入口）。

### Deliverables

- `miniapp/src/pages.json`（路由与 tabbar）
- `miniapp/src/manifest.json`（uni-app 配置）
- `miniapp/src/main.ts`、`miniapp/src/App.vue`
- `miniapp/src/utils/api.ts`（请求封装：token/401）
- `miniapp/src/utils/navigation.ts`（redirect 组装与跳登录）
- `miniapp/src/utils/storage.ts`（token 存储）
- `miniapp/src/pages/**/index.vue`（页面壳）

### Verification

- 能打开任一页面（首页/搜索/登录等），页面有可见文字。
- `toLogin()` 会跳转到 `/pages/login/index?redirect=...`。
- 登录页点击“模拟登录并回跳”会写入 `accessToken` 并 `reLaunch` 回原页面。

### Exit criteria

- 工程结构固定；后续页面实现只在此基础上填充业务逻辑，不再改动路由与请求层骨架。

