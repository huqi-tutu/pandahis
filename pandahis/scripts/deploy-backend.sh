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
# 优先使用 ~/.ssh/config 中的 histomap 别名（IdentitiesOnly + 指定密钥）
SSH_TARGET="${SSH_TARGET:-histomap}"
REMOTE_DIR="${REMOTE_DIR:-/opt/histomap-api}"
SERVICE_NAME="${SERVICE_NAME:-histomap-api}"

export JAVA_HOME="${JAVA_HOME:-$(brew --prefix openjdk@17 2>/dev/null)/libexec/openjdk.jdk/Contents/Home}"
if [[ -n "${JAVA_HOME}" && -d "${JAVA_HOME}" ]]; then
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi

echo "==> 1/4 打包 backend"
if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
  echo "    跳过打包（SKIP_BUILD=1）"
else
  cd "$BACKEND"
  bash mvnw -q clean package -DskipTests
fi
test -f "$JAR"

SSH_OPTS=(
  -o IdentitiesOnly=yes
  -o PreferredAuthentications=publickey,keyboard-interactive,password
  -o PubkeyAuthentication=yes
  -o ControlPath="$HOME/.ssh/cm-%r@%h:%p"
)

REMOTE="${SSH_TARGET}"
echo "==> 2/4 上传 JAR 到 ${REMOTE}:${REMOTE_DIR}/"
ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p '${REMOTE_DIR}'"
scp "${SSH_OPTS[@]}" "$JAR" "${REMOTE}:${REMOTE_DIR}/histomap-api-0.1.0.jar"

echo "==> 3/4 重启 ${SERVICE_NAME}"
if ssh "${SSH_OPTS[@]}" "$REMOTE" "systemctl is-enabled ${SERVICE_NAME} >/dev/null 2>&1"; then
  ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo systemctl restart ${SERVICE_NAME} && sudo systemctl is-active ${SERVICE_NAME}"
elif ssh "${SSH_OPTS[@]}" "$REMOTE" "command -v pm2 >/dev/null 2>&1 && pm2 describe ${SERVICE_NAME} >/dev/null 2>&1"; then
  # 确保进程从正确目录以绝对路径启动，避免仍跑旧 JAR
  ssh "${SSH_OPTS[@]}" "$REMOTE" "pm2 delete ${SERVICE_NAME} >/dev/null 2>&1 || true; pm2 start java --name ${SERVICE_NAME} --cwd '${REMOTE_DIR}' -- -jar '${REMOTE_DIR}/histomap-api-0.1.0.jar' && pm2 save"
else
  echo "未找到 systemd / pm2 服务 ${SERVICE_NAME}，请手动重启 Java 进程。"
  exit 1
fi

echo "==> 4/4 健康检查"
sleep 8
curl -fsS "https://www.pandahis.com/api/v1/health" | python3 -m json.tool
# 冒烟：搜索不应再 INTERNAL_ERROR；头像路由应存在（无登录为 UNAUTHORIZED/INVALID，不是 NOT_FOUND）
SEARCH_CODE=$(curl -sS "https://www.pandahis.com/api/v1/search?q=test" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("code"))')
AVATAR_CODE=$(curl -sS -X POST "https://www.pandahis.com/api/v1/me/avatar" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("code"))')
echo "smoke search=${SEARCH_CODE} avatar=${AVATAR_CODE}"
if [[ "${SEARCH_CODE}" == "INTERNAL_ERROR" ]]; then
  echo "警告：搜索仍返回 INTERNAL_ERROR" >&2
  exit 1
fi
if [[ "${AVATAR_CODE}" == "NOT_FOUND" ]]; then
  echo "警告：头像接口仍为 NOT_FOUND（可能未加载新 JAR）" >&2
  exit 1
fi
echo
echo "部署完成。"
