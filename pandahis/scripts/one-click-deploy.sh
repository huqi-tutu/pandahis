#!/usr/bin/env bash
# 一键：建立 SSH 主控连接 + 部署后端
# 用法：在终端中执行此脚本，扫码后自动完成全部部署

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
JAR="$ROOT/backend/target/histomap-api-0.1.0.jar"
REMOTE="root@49.235.165.220"
REMOTE_DIR="/opt/histomap"

echo "========================================"
echo "  建立 SSH 主控连接（请扫码）"
echo "========================================"
ssh -MNf -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$REMOTE" || {
  echo -e "\n扫码认证后请等待连接建立..."
  ssh -MNf -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$REMOTE"
}

echo "SSH 主控连接已建立！"

echo ""
echo "==> 上传 JAR..."
scp -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$JAR" "${REMOTE}:${REMOTE_DIR}/histomap-api-0.1.0.jar"

echo ""
echo "==> 重启服务..."
if ssh -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$REMOTE" "systemctl is-enabled histomap-api >/dev/null 2>&1"; then
  ssh -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$REMOTE" "sudo systemctl restart histomap-api && sudo systemctl is-active histomap-api"
elif ssh -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$REMOTE" "command -v pm2 >/dev/null 2>&1"; then
  ssh -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$REMOTE" "pm2 restart histomap-api 2>/dev/null || pm2 start ${REMOTE_DIR}/histomap-api-0.1.0.jar --name histomap-api"
fi

echo ""
echo "==> 健康检查..."
sleep 3
curl -fsS "https://www.pandahis.com/api/v1/health" 2>/dev/null && echo "" && echo "部署成功！" || echo "(请稍后手动验证)"

echo ""
echo "主控连接保持活跃（10分钟），Cursor 现在可复用此连接。"
