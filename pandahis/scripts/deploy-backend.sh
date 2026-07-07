#!/usr/bin/env bash
# 打包并部署 histomap-api 到生产服务器
# 用法：
#   SSH_HOST=49.235.165.220 SSH_USER=root ./scripts/deploy-backend.sh
# 首次使用前请确保本机可 ssh $SSH_USER@$SSH_HOST（公钥或密码）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
JAR="$BACKEND/target/histomap-api-0.1.0.jar"

SSH_HOST="${SSH_HOST:-49.235.165.220}"
SSH_USER="${SSH_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/opt/histomap}"
SERVICE_NAME="${SERVICE_NAME:-histomap-api}"

export JAVA_HOME="${JAVA_HOME:-$(brew --prefix openjdk@17 2>/dev/null)/libexec/openjdk.jdk/Contents/Home}"
if [[ -n "${JAVA_HOME}" && -d "${JAVA_HOME}" ]]; then
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi

echo "==> 1/4 打包 backend"
cd "$BACKEND"
bash mvnw -q clean package -DskipTests
test -f "$JAR"

REMOTE="${SSH_USER}@${SSH_HOST}"
echo "==> 2/4 上传 JAR 到 ${REMOTE}:${REMOTE_DIR}/"
ssh "$REMOTE" "mkdir -p '${REMOTE_DIR}'"
scp "$JAR" "${REMOTE}:${REMOTE_DIR}/histomap-api-0.1.0.jar"

echo "==> 3/4 重启 ${SERVICE_NAME}"
if ssh "$REMOTE" "systemctl is-enabled ${SERVICE_NAME} >/dev/null 2>&1"; then
  ssh "$REMOTE" "sudo systemctl restart ${SERVICE_NAME} && sudo systemctl is-active ${SERVICE_NAME}"
elif ssh "$REMOTE" "command -v pm2 >/dev/null 2>&1 && pm2 describe ${SERVICE_NAME} >/dev/null 2>&1"; then
  ssh "$REMOTE" "pm2 restart ${SERVICE_NAME}"
else
  echo "未找到 systemd / pm2 服务 ${SERVICE_NAME}，请手动重启 Java 进程。"
  exit 1
fi

echo "==> 4/4 健康检查"
sleep 2
curl -fsS "https://www.pandahis.com/api/v1/health" | python3 -m json.tool
echo
echo "部署完成。"
