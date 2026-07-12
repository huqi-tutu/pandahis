#!/usr/bin/env bash
# 微信开发者工具会编译项目内全部 .ts；任一文件报错会导致整包（含首页）编译失败。
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -d node_modules/typescript ]]; then
  npm install --no-save typescript miniprogram-api-typings >/dev/null
fi
npx tsc --noEmit -p tsconfig.json
echo "miniapp TypeScript check passed"
echo "Tip: run npm run build:ts to emit JS before opening WeChat DevTools"
