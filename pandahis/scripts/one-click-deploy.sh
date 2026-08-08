#!/usr/bin/env bash
# 一键：微信扫码建立 SSH 主控连接 + 部署后端
# 用法：bash scripts/one-click-deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JAR="$ROOT/backend/target/histomap-api-0.1.0.jar"
SSH_TARGET="${SSH_TARGET:-histomap}"
REMOTE_DIR="${REMOTE_DIR:-/opt/histomap-api}"
SERVICE_NAME="${SERVICE_NAME:-histomap-api}"
CONTROL_PATH="$HOME/.ssh/cm-%r@%h:%p"

export JAVA_HOME="${JAVA_HOME:-$(brew --prefix openjdk@17 2>/dev/null)/libexec/openjdk.jdk/Contents/Home}"
if [[ -n "${JAVA_HOME}" && -d "${JAVA_HOME}" ]]; then
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi

ssh_common_opts=(
  -o ControlPath="$CONTROL_PATH"
  -o IdentitiesOnly=yes
  -o PreferredAuthentications=publickey,keyboard-interactive,password
  -o PubkeyAuthentication=yes
)

control_ready() {
  ssh "${ssh_common_opts[@]}" -O check "$SSH_TARGET" >/dev/null 2>&1
}

ensure_control_master() {
  if control_ready; then
    echo "==> 复用已有 SSH 主控连接"
    return 0
  fi

  echo "========================================"
  echo "  请在弹出的终端窗口用微信扫码登录"
  echo "========================================"

  osascript <<EOF 2>/dev/null || true
tell application "Terminal"
  activate
  do script "ssh -MN -o ControlPath=\"$CONTROL_PATH\" -o IdentitiesOnly=yes -o PreferredAuthentications=publickey,keyboard-interactive,password -o PubkeyAuthentication=yes $SSH_TARGET"
end tell
EOF

  echo "等待扫码建立连接（最多 10 分钟）..."
  local waited=0
  while ! control_ready; do
    sleep 3
    waited=$((waited + 3))
    if (( waited >= 600 )); then
      echo "超时：仍未建立 SSH 主控连接。请手动扫码后重试。"
      exit 1
    fi
    if (( waited % 15 == 0 )); then
      echo "  ...仍在等待扫码 (${waited}s)"
    fi
  done
  echo "SSH 主控连接已建立！"
}

echo "==> 1/4 打包 backend"
cd "$ROOT/backend"
bash mvnw -q clean package -DskipTests
test -f "$JAR"

ensure_control_master

echo ""
echo "==> 2/4 上传 JAR 到 ${SSH_TARGET}:${REMOTE_DIR}/"
ssh "${ssh_common_opts[@]}" "$SSH_TARGET" "mkdir -p '${REMOTE_DIR}'"
scp "${ssh_common_opts[@]}" "$JAR" "${SSH_TARGET}:${REMOTE_DIR}/histomap-api-0.1.0.jar"

echo ""
echo "==> 3/4 重启 ${SERVICE_NAME}"
if ssh "${ssh_common_opts[@]}" "$SSH_TARGET" "systemctl is-enabled ${SERVICE_NAME} >/dev/null 2>&1"; then
  ssh "${ssh_common_opts[@]}" "$SSH_TARGET" "sudo systemctl restart ${SERVICE_NAME} && sudo systemctl is-active ${SERVICE_NAME}"
elif ssh "${ssh_common_opts[@]}" "$SSH_TARGET" "command -v pm2 >/dev/null 2>&1"; then
  ssh "${ssh_common_opts[@]}" "$SSH_TARGET" "pm2 restart ${SERVICE_NAME} 2>/dev/null || pm2 start ${REMOTE_DIR}/histomap-api-0.1.0.jar --name ${SERVICE_NAME}"
else
  echo "未找到 systemd / pm2 服务 ${SERVICE_NAME}，请手动重启 Java 进程。"
  exit 1
fi

echo ""
echo "==> 4/4 健康检查"
sleep 3
curl -fsS "https://www.pandahis.com/api/v1/health" | python3 -m json.tool
echo ""
echo "部署完成。"
