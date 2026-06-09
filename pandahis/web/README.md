# Pandahis Web（产品呈现端）

这个 `web/` 不是“系统实现介绍页”，而是**把 PRD + 原型的产品体验在 Web 上跑起来**的一端：
- 图谱首页（时空矩阵）
- 历史单元详情（年份 × 五类分类矩阵）
- 历史盒子详情（详情 / 关系图谱 / 评述 / 文物）
- 搜索（热门/历史/结果）
- 会员 / 我的 / 登录（展示与引导）

目前阶段：**不接后端接口**，直接复用 Excel 内容作为静态数据源，确保“别人一访问就能爱上这个产品”的体验优先。

## UI 灵感来源与许可

本项目部分交互/视觉效果参考了 Uiverse 的开源 UI 组件风格（如 spotlight 卡片、光晕 hover、发光按钮等）。
Uiverse Galaxy 仓库为 MIT License：见 [uiverse-io/galaxy](https://github.com/uiverse-io/galaxy)。

本项目的部分动效（如关系图谱的连线绘制、节点弹出、节奏控制）使用 Anime.js（MIT License）：见 [juliangarnier/anime](https://github.com/juliangarnier/anime)。

## 本地启动

```bash
cd web
npm i
npm run dev
```

打开 `http://127.0.0.1:5173/explore`

## Excel 数据源（当前已接入）

- 源文件：`prd/历史图谱 - 首页数据.xlsx`
- 导入脚本：`web/scripts/import_home_xlsx.py`
- 生成数据：`web/src/data/generated.json`（前端直接 import）
- 前端入口：`web/src/data/content.ts`

当 Excel 更新后，重新生成一次：

```bash
python web/scripts/import_home_xlsx.py
```

## “自行理解补充”的生成规则（v1）

你的 Excel 当前提供的是「历史盒子」维度的结构字段（ID、朝代、帝王、单元名、年号、起止年份、重要性、备注、文明体系、标签等）。
但产品体验还需要：
- 五类分类（君纪/士臣/民录/典制/事略）
- 盒子详情正文
- 关系图谱、跨时空评述、文物见证

为让 Web 端先成为“产品的一端”，当前采用可解释的自动补全规则（写在 `import_home_xlsx.py`）：

- **Unit 分组规则**：按 `(文明体系, 历史单元名称, 朝代名称, 帝王名称, 年号)` 聚合为一个历史单元；单元的 `startYear/endYear` 取 min/max。
- **Category 推断规则**：依据 `备注/标签/ID` 的关键词命中（登基/改元/法制/民变等）推断到五类；若都未命中，则对 `box_id` 做稳定哈希后分配。
- **详情正文生成**：基于「单元名/朝代/帝王/年号/备注/标签」生成 3~4 段“叙事化”文本（风格接近原型但不做事实扩写）。
- **评述生成**：按重要性生成 1~3 条“多视角”评述卡片（占位但可读）。
- **文物生成**：重要性高的内容生成 0~2 条“文物卡片占位”（后续你可补真名称/馆藏/图片）。
- **关系图谱生成**：以事件为中心，附加帝王/朝代/标签节点，输出 nodes/edges（可直接渲染）。

> 这些规则的目标是：不乱编事实，但把“结构与体验”先完整呈现出来。后续你补齐更细粒度字段（正文、评述、文物、关系），导入脚本可以无缝替换为真实内容。

