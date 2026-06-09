## 联调 Checklist（V5 对齐 + TDD 自检）

> 自动化：`cd backend && ./mvnw test`（7 项集成测试，GitHub Actions `CI` workflow）  
> 手工：微信开发者工具 + [`e2e-smoke.md`](./e2e-smoke.md)

### SCREEN01 首页 · 沉浸政权矩阵（产品 1:1）

**数据**：矩阵几何 Phase 1 走客户端 `native-utils/matrix/mock-home-matrix.js`；`/home/grid` 供地图 URL + unitId 映射；`/home/matrix` 保留供 Phase 4 迁移。

**视觉/交互验收（对照产品 home-matrix + home-overview）**

- [ ] 默认沉浸 matrix，18 文明 stack 层叠卡片（`stackMode=true`）
- [ ] 矩阵下滑 ~130px：图片 Tab morph 为文字 Tab，Tab 区 147→88rpx
- [ ] 左轴朝代 ↑/↓ 展开（华夏神宗/哲宗等，`onDynastyToggle`）
- [ ] 春秋战国 8 列 regime mosaic（`regime-era-layout`）
- [ ] 政权块 seam 无白缝、L 形拼接（`fillSeamFix` classes）
- [ ] 点击块 → `unit-detail?unitId=&anchorYear=`
- [ ] Nav 左 pill（quanbu）开顶部 civ picker（非 bottom sheet）
- [ ] Nav 右 pill「总览 ▾」→ overview：13 热区 + 8 段 era bar + gradient civ grid
- [ ] Overview 点文明 → 回 matrix 并选中对应 civ
- [ ] Loading「同步历史数据…」脉冲样式
- [ ] 配图资产：`/配图/文明tab配图/*.png`、`/images/world-history-dynasty-map.png` 无 404

**API（后端 / Phase 4）**

- [ ] `GET /home/grid` 返回 `timeAxis/civilizations/cells/overview`
- [ ] `GET /home/matrix?civId=` 返回 `rows/blocks/overlays/totalHRpx`（含 seam 扩展字段）
- [ ] `blocks` 含 `leftPct/widthPct/unitId/anchorYear/entryId/fillSeamFix`
- [ ] `GET /home/matrix?civId=&expanded=dyn_song_hx` 展开后块数增加

### SCREEN02 历史单元详情 · 泳道矩阵

- [ ] `GET /units/{unitId}` 返回 hero + relatedUnits + nextUnit
- [ ] `GET /units/{unitId}/swim-matrix` 返回 5 lanes（君纪/士臣/典制/事略/民录）
- [ ] 泳道 bar 含 `boxId/left/width/layout`；`hasMore` 时显示 +N
- [ ] 小程序：三态 layout（shichen/continuous/isolated）渲染
- [ ] 小程序：横向时间轴吸顶（`axisPinned`）
- [ ] `anchorYear` 参数横向滚动定位

### SCREEN03-06 盒子详情与 tabs

- [ ] `GET /boxes/{boxId}` 返回 tabSummary + access
- [ ] `GET /boxes/{boxId}/graph/nodes/{nodeKey}` 返回关系详情字段
- [ ] 详情 Tab 底部四宫格：原文 / 播放 / 收藏 / 分享
- [ ] 评述/见证/关系节点 → 独立详情页（非 modal）
- [ ] 关系 Tab 底部缩放胶囊（− / 比例 / +）
- [ ] 音频全屏 overlay（播放进度）

### SCREEN07-08 搜索

- [ ] `GET /search/suggest` + `GET /search?q=`
- [ ] 搜索 Tab → 独立 `search-result` 页
- [ ] 结果页分类筛选（全部/君纪/士臣/典制/事略/民录）

### SCREEN09 我的

- [ ] `GET /me` 含 `learnDaysCount`（足迹按日去重）
- [ ] hero 三列：足迹 / 收藏 / 学习天

### SCREEN10-11 会员与登录

- [ ] `POST /auth/wx-login` 登录成功
- [ ] 登录页 Logo + slogan；手机号 UI（后端暂未开放，预期 toast）

### Known gaps（产品稿有、当前未实现）

- [ ] `critique-list` 独立页 + 点赞/评论（无 DB/API）
- [ ] 手机号 SMS 登录（无 `/auth/phone`）
- [ ] 首页矩阵完整 `regime-era-layout` 合并规则（**客户端已 1:1**；后端 Phase 4 迁移中，DTO 已预留 seam 字段）
- [ ] 泳道「著作/思想」两 lane（产品 mock 有，后端仅 5 分类）

### 遗留 API（仍可用）

- [ ] `GET /units/{unitId}/matrix` 年份×分类网格（旧视图，泳道为主）
- [ ] `GET /units/{unitId}/civ-tabs` 跨文明 Tab
