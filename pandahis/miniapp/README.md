## 历史图谱小程序（原生微信小程序）

本目录为**原生微信小程序**工程（对齐参考项目 `project/pandahis` 的 `custom-tab-bar`、`navigation-bar`、`glass-card` 等结构），不依赖 npm / HBuilderX。

### 运行方式

1. 打开微信开发者工具，**导入**本目录：`pandahis/miniapp`
2. 页面逻辑为 **`index.ts`**、样式为 **`*.scss`**。微信开发者工具仅开启 **`sass`** 插件（SCSS→WXSS）；**TypeScript 在本地预编译**为 `.js`（见下），避免工具内 TS 全量编译超时。
3. **改完 `.ts` 后请执行** `npm run build:ts`（类型检查：`npm run check:ts`）。存在 `index.ts` 的页面以 TS 为唯一源码，不要手改编译产物 `.js`。
4. **编译范围**：若重新开启微信的 `typescript` 插件，工具会编译项目内**全部** `.ts`，任一报错会导致整包（含首页）失败。
5. 改完 TS 后可在本目录执行 **`npm run check:ts`**（或 `bash scripts/check-ts.sh`）提前发现类型错误。
6. **WXML 注意**：表达式里请使用 `==` 而不是 `===`；同一节点不要同时写 `wx:if`/`wx:elif` 与 `wx:for`；自定义组件尽量写成 `<comp></comp>` 闭合形式（避免 `/>` 在旧解析器上报错）。
7. **若模拟器报 `Error: timeout`（`WAServiceMainContext.js` + 基础库 3.15.x）**：多为开发者工具已知问题，与业务代码无关。本项目已将 **`libVersion` 固定为 `3.14.5`**；请在 **详情 → 本地设置** 将调试基础库也选为 **3.14.x**，并 **清缓存 → 重新编译**。
8. **真机预览报 80051 / 超过 2MB**：主包默认上限 2MB。已开启 **`bigPackageSizeSupport`**（预览上限 4MB），且 **`.miniprogramignore` 排除 `*.ts`**（只上传编译后的 `.js`）。改 TS 后先 `npm run build:ts` 再预览。若仍超限，在开发者工具 **详情 → 本地设置** 确认已勾选「预览及真机调试时主包、分包体积上限调整为 4M」。
9. 若 SCSS 不编译：检查 `project.private.config.json` 的 `useCompilerPlugins` 是否包含 `sass`。
10. 启动后端（默认 `http://localhost:8080`），保证可访问 `GET /api/v1/health`（如有）

### 后端联调

- 开发版会自动选择 API 地址：
  - **开发者工具**：`http://localhost:8080/api/v1`
  - **真机预览**：`https://www.pandahis.com/api/v1`，避免开发机局域网 IP 变化导致页面空白
- 开发版真机需要联调本地后端时，可在调试器 Console 手动覆盖：
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
