#!/usr/bin/env bash
# 一键上传 JAR 并重启后端服务（已打包好的 JAR）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JAR="$ROOT/backend/target/histomap-api-0.1.0.jar"
REMOTE="root@49.235.165.220"
REMOTE_DIR="/opt/histomap"

echo "==> 上传 JAR..."
scp "$JAR" "${REMOTE}:${REMOTE_DIR}/histomap-api-0.1.0.jar"

echo "==> 重启服务..."
if ssh "$REMOTE" "systemctl is-enabled histomap-api >/dev/null 2>&1"; then
  ssh "$REMOTE" "sudo systemctl restart histomap-api && sudo systemctl is-active histomap-api"
elif ssh "$REMOTE" "command -v pm2 >/dev/null 2>&1"; then
  ssh "$REMOTE" "pm2 restart histomap-api 2>/dev/null || pm2 start ${REMOTE_DIR}/histomap-api-0.1.0.jar --name histomap-api"
else
  echo "重启服务失败：未找到 systemd 或 pm2"
  exit 1
fi

echo "==> 健康检查..."
sleep 2
curl -fsS "https://www.pandahis.com/api/v1/health" 2>/dev/null || echo "(健康检查暂不可用，稍后验证)"

echo "部署完成！"
