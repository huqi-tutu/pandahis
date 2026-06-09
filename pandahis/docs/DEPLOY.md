# 三端发布打包与部署

## 共同前提

- Linux 服务器（或等价），已安装 **Nginx** 与 **Java 17+**。
- 后端对外前缀：`server.servlet.context-path: /api/v1`（见 `backend/src/main/resources/application.yaml`）。

---

## 1. 后端（Spring Boot）

### 1.1 打包

在 `backend` 目录：

```bash
# Windows
.\mvnw.cmd clean package -DskipTests

# Linux / macOS
./mvnw clean package -DskipTests
```

产物：`backend/target/histomap-api-0.1.0.jar`（版本以 `pom.xml` 为准）。

### 1.2 生产配置

- 使用 **`prod` profile**：`SPRING_PROFILES_ACTIVE=prod`，加载 `application-prod.yaml`（MySQL、`spring.sql.init.mode: never`、排除未使用的 Redis 自动配置）。
- 默认数据源在 `application.yaml` 与 `application-prod.yaml` 中一致（同一 MySQL）；若需改连接，可设 `SPRING_DATASOURCE_URL` / `SPRING_DATASOURCE_USERNAME` / `SPRING_DATASOURCE_PASSWORD` / `SPRING_DATASOURCE_DRIVER_CLASS_NAME` 覆盖。

### 1.3 数据库初始化（首次）

生产不执行 `spring.sql.init`，请在 MySQL 中建库后，按顺序执行（路径相对 `backend/src/main/resources`）：

1. `schema.sql`
2. `schema_user.sql`
3. `schema_search.sql`
4. `schema_membership.sql`
5. 按需执行 `data.sql` 作为种子数据（或自行导入）

### 1.4 后台持续运行（不要只在前台 `java -jar`）

在 SSH 里直接执行 `java -jar ...` 是**前台进程**：关掉终端或断开 SSH，进程通常会结束，也无法在开机后自动拉起。

**推荐：用 systemd 守护**（断开 SSH 后仍运行，崩溃可自动重启，可设开机自启）。

示例单元：`deploy/histomap-api.service`。可选环境文件：`deploy/api.env.example`（复制为 `/etc/histomap/api.env`，`chmod 600`）。

```bash
sudo mkdir -p /opt/histomap /etc/histomap
# 上传 JAR 到 /opt/histomap/histomap-api-0.1.0.jar（版本以 pom 为准）
sudo cp deploy/histomap-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable histomap-api    # 开机自启
sudo systemctl start histomap-api     # 立即启动
```

常用命令：`sudo systemctl status histomap-api`、`sudo journalctl -u histomap-api -f`（看日志）、`sudo systemctl restart histomap-api`。

若单元里 `User=www-data` 与你的环境不符，可改成 `root` 或自建用户，并保证该用户对 `/opt/histomap` 下 JAR 有读权限。

**备选：PM2**（你已在服务器上用 PM2 管 Node 时很方便；同样可以后台常驻、自动重启、开机拉起）。

示例：`deploy/pm2-ecosystem.config.cjs`（把其中 JAR 路径、版本号改成服务器上的实际路径）。

```bash
npm i -g pm2   # 若尚未安装
# 编辑 pm2-ecosystem.config.cjs 中的 -jar 路径后：
pm2 start deploy/pm2-ecosystem.config.cjs
pm2 logs histomap-api
pm2 save
pm2 startup    # 按终端提示执行一条 sudo，写入 systemd 实现开机自启
```

**临时方案（无进程管理器、仅测试）**：`nohup java -jar histomap-api-0.1.0.jar --spring.profiles.active=prod > /var/log/histomap-api.log 2>&1 &`  
然后 `disown` 或记下 PID；不如 systemd / PM2 可靠。

### 1.5 Nginx 反代

示例配置：`deploy/nginx-histomap.conf`。要点：

- 静态站点 `root` 指向 Web 的 `dist` 目录。
- `location /api/v1/` → `proxy_pass http://127.0.0.1:8080/api/v1/;`（注意尾部 `/`，避免路径重复拼接错误）。

### 1.6 健康检查

```bash
curl -sS https://your-domain.com/api/v1/health
```

---

## 2. Web（Vite + React）

### 2.1 构建

在 `web` 目录：

```bash
npm ci
npm run build
```

产物：`web/dist`，部署到服务器后由 Nginx `root` 指向该目录（见 `deploy/nginx-histomap.conf`）。

### 2.2 子路径部署

若站点不在域名根路径（例如 `https://domain.com/app/`），在 `web/vite.config.ts` 中设置 `base: '/app/'` 后重新执行 `npm run build`。

---

## 3. 微信小程序

### 3.1 上传

1. 使用 **微信开发者工具** 打开仓库中的 `miniapp` 目录。
2. 确认 `miniapp/project.config.json` 中 `appid` 为正式小程序 AppID。
3. **上传** → 微信公众平台提交审核并发布。

### 3.2 合法域名与 API 基址

- 在小程序后台配置 **request 合法域名** 为你的 **HTTPS** 根地址，须与客户端拼接方式一致（见 `miniapp/native-utils/api.ts`：`baseUrl + path`，`path` 以 `/` 开头）。
- 正式环境在真机/体验版前任选其一：
  - 通过产品内「环境设置」写入 `wx.setStorageSync('apiBaseUrl', 'https://your-domain.com/api/v1')`；或
  - 将代码中 `DEFAULT_BASE_URL` 改为生产 HTTPS 地址后重新上传。

勿让体验版仍指向 `localhost`。

---

## 4. 建议发布顺序

1. 部署 MySQL 并执行 schema → 启动后端与 Nginx → 验证 `/api/v1/health`。
2. 部署 Web 静态资源，确认无 404。
3. 配置小程序合法域名与 `apiBaseUrl`，真机预览后上传提审。
