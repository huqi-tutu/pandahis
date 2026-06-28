## 历史图谱小程序（原生微信小程序）

本目录为**原生微信小程序**工程（对齐参考项目 `project/pandahis` 的 `custom-tab-bar`、`navigation-bar`、`glass-card` 等结构），不依赖 npm / HBuilderX。

### 运行方式

1. 打开微信开发者工具，**导入**本目录：`pandahis/miniapp`
2. 页面逻辑为 **`index.ts`**、样式为 **`*.scss`**，已在 `project.config.json` 中开启 **`useCompilerPlugins: ["typescript", "sass"]`**：TS 编成 JS、SCSS 编成 WXSS。若删掉 **`sass`**，页面会几乎没有任何样式（只有纯文字）。
3. **WXML 注意**：表达式里请使用 `==` 而不是 `===`；同一节点不要同时写 `wx:if`/`wx:elif` 与 `wx:for`；自定义组件尽量写成 `<comp></comp>` 闭合形式（避免 `/>` 在旧解析器上报错）。
4. 若 TS/SCSS 不编译：请将微信开发者工具升级到较新版本（官方 TS 插件说明见[编译 TS](https://developers.weixin.qq.com/miniprogram/dev/devtools/compilets.html)），并检查 `project.private.config.json` 是否把 `useCompilerPlugins` 改成了不含 `sass`/`typescript` 的值。
5. 启动后端（默认 `http://localhost:8080`），保证可访问 `GET /api/v1/health`（如有）

### 后端联调

- 开发版会自动选择 API 地址：
  - **开发者工具**：`http://localhost:8080/api/v1`
  - **真机预览**：`http://<局域网IP>:8080/api/v1`（当前配置见 `native-utils/dev-config.ts`）
- 换 WiFi 或 IP 变化时，修改 `native-utils/dev-config.ts` 中的 `DEV_LAN_HOST`
- 手动覆盖：在调试器 Console 执行  
  `wx.setStorageSync('apiBaseUrl', 'http://<本机IP>:8080/api/v1')`

### 合法域名 / localhost 请求失败

若控制台出现 **「不在以下 request 合法域名列表中」**：

1. **推荐（本项目已配置）**：`project.config.json` 与 `project.private.config.json` 中 `setting.urlCheck` 均为 **`false`**，开发工具将**不校验** request 合法域名（上传正式版前仍须在[小程序后台](https://mp.weixin.qq.com/)配置服务器域名）。
2. **若仍被拦截**：在微信开发者工具打开 **详情 → 本地设置**，勾选 **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**。
3. **真机预览**：真机默认会校验域名；需使用已备案 **HTTPS** 域名并在后台配置为 request 合法域名，或使用内网穿透得到 HTTPS 后再配置。

### 登录（开发态）

后端 `BearerAuthFilter` 将**任意非空** Bearer Token 视为已登录用户。请先打开 **登录** 页执行「一键写入 Token」，再使用收藏、足迹、会员、搜索历史清除等需鉴权接口。

### 已实现页面与接口

| 页面 | 主要接口 |
|------|----------|
| 首页 | `GET /home/grid` |
| 搜索 | `GET /search/suggest`、`GET /search`、`DELETE /search/history`（需登录） |
| 单元详情 | `GET /units/{id}`、`GET /units/{id}/matrix` |
| 盒子详情 | `GET /boxes/{id}`、详情/图谱/评述/文物子接口；`POST /footprints/.../view`（需登录）；收藏 `POST/DELETE /favorites/boxes/{id}` |
| 我的 / 收藏 / 足迹 | `GET /me`、`GET /favorites/boxes`、`GET /footprints/boxes` |
| 会员 | `GET /membership/plans`、`GET /membership`、`POST /orders`、`POST /payments/wechat/notify` |
| 原文 | `GET /boxes/{id}/detail` 中的 `originalRef` 展示 |
| 登录 | 本地写入 `accessToken`（预留 `wx.login` 探测） |
