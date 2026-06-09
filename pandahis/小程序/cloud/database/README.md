# 首页矩阵 · 数据说明

**首页已改回本地写死**，不依赖云数据库。

| 文件 | 说明 |
|------|------|
| `数据/王朝表.json` | 编辑源（JSONL + 中文列名） |
| `数据/帝王表.json` | 编辑源（含 `标签` 字段） |
| `data/dynasty-data.js` | 构建产物，小程序直接 require |
| `data/emperor-data.js` | 构建产物，小程序直接 require |

修改 `数据/` 下 JSON 后执行：

```bash
node scripts/build-local-matrix-data.js
```

然后重新编译小程序。

---

# 云数据库（可选，首页未使用）

## 集合

| 集合名 | 说明 | 数据来源 |
|--------|------|----------|
| `atlas_dynasties` | 王朝/政权表 | `数据/王朝表.json` |
| `atlas_emperors` | 帝王表 | `数据/帝王表.json` |

## 字段（与本地 JSON 对齐）

### atlas_dynasties

```json
{
  "_id": "HX-T",
  "id": "HX-T",
  "name": "唐",
  "dynasty": "唐",
  "dynasty_zy": "唐",
  "dynasty2": "唐",
  "civilization": "华夏",
  "start": "618",
  "end": "907"
}
```

### atlas_emperors

```json
{
  "_id": "zhong_hua_tang_li_shi_min",
  "id": "zhong_hua_tang_li_shi_min",
  "name": "李世民",
  "dynasty": "唐",
  "dynasty2": "唐",
  "start": "626",
  "end": "649",
  "years": "23",
  "temple": "太宗",
  "era": "贞观",
  "importance": "5",
  "tag": "玄武门之变,贞观之治"
}
```

`tag`（或中文键 `标签`）为可选字段，逗号分隔 1–2 条大事标签；值为 `-` 或空表示无标签。
导入前请确认 JSON 含该字段，并运行 `node scripts/build-cloud-seed-json.js` 从 `数据/帝王表.json` 生成 seed。

## 数据文件格式

`数据/王朝表.json`、`数据/帝王表.json` 支持两种写法：

1. **标准 JSON 数组**（英文列名）
2. **JSONL**（每行一条，可用中文列名，如 `标签`、`历史盒子 ID`、`即位时间`）

生成 seed 时会自动映射为云库标准字段（含 `tag`）：

```bash
node scripts/build-cloud-seed-json.js
```

帝王表中文列名对照：`历史盒子 ID`→`id`，`帝王`→`name`，`政权`→`dynasty2`，`朝代`→`dynasty`，`即位时间`→`start`，`退位时间`→`end`，`标签`→`tag`

## 权限建议

- **读**：所有用户可读
- **写**：仅管理员 / 云函数

## 初始化步骤

1. 微信开发者工具开通云开发，创建环境，将环境 ID 写入 `config/cloud.env.js`
2. 在云开发控制台创建集合：`atlas_dynasties`、`atlas_emperors`
3. 本地生成 seed 文件并上传云函数：

```bash
cd 历史图谱/小程序
node scripts/build-cloud-seed-json.js
```

4. 右键 `cloudfunctions/seedHomeMatrixData` → **上传并部署：云端安装依赖**（勿选「所有文件」，勿上传本地 node_modules）
5. 云开发控制台 → 云函数 → `seedHomeMatrixData` → 测试运行，参数 **`{}`**（首次导入）或 **`{"clear":true}`**（清空后重导）
   - 成功时 `remaining` 应为：`dynasties: 222`，`emperors: 434`
   - 若 `remaining` 为 0，看返回的 `message` / `errors` 字段
6. 右键 `cloudfunctions/getHomeMatrixData` → **上传并部署：云端安装依赖**
7. 重新编译小程序，进入首页验证

## 清空云库（仅删除，不重新导入）

1. 右键 `cloudfunctions/clearHomeMatrixData` → **上传并部署：云端安装依赖**
2. 云开发控制台 → 云函数 → `clearHomeMatrixData` → **测试运行**，参数 `{}`
3. 返回示例：

```json
{
  "code": 0,
  "data": {
    "removed": { "dynasties": 209, "emperors": 399 },
    "remaining": { "dynasties": 0, "emperors": 0 }
  }
}
```

也可用 `seedHomeMatrixData` 测试参数 `{"clearOnly": true}` 达到同样效果。
