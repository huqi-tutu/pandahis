# 泳道图 flat 布局备份（v1）

备份时间：2026-05-26

## 包含文件

- `dynasty-detail.wxml`
- `dynasty-detail.js`
- `dynasty-detail.wxss`
- `mock-dynasty.js`

## 回滚方式

将本目录下 4 个文件复制回对应位置即可：

```bash
cp _backup-v1-flat-swimlane/dynasty-detail.* .
cp _backup-v1-flat-swimlane/mock-dynasty.js ../../data/
```

## 变更说明

v2 仅对「士臣」泳道启用 3D 透视堆叠 + 上下拖拽切换层，其他泳道保持 flat 布局不变。
