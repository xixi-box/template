# 📦 项目配置模板库

个人项目通用配置模板集合，新项目按需取用，替换 `<占位符>` 即可。

---

## 🐳 Docker 镜像

| 模板 | 说明 |
|------|------|
| [Dockerfile.java-service](Dockerfile.java-service) | Spring Boot Java 服务运行时（JRE Alpine + 非root用户 + HEALTHCHECK + ENV fallback），由 9 个重复 Dockerfile 合并 |
| [Dockerfile.java-dev-build](Dockerfile.java-dev-build) | Java 服务多阶段构建版（Maven 编译 → JRE 运行），CI 环境无构建能力时使用 |
| [Dockerfile.java-playwright](Dockerfile.java-playwright) | Playwright 浏览器自动化服务（截图/E2E），基于 Ubuntu Noble + Chromium |
| [Dockerfile.vue-nginx](Dockerfile.vue-nginx) | Vue/React SPA + Nginx 生产镜像，含纯运行时和多阶段构建两种方案 |

## 🌐 Nginx

| 模板 | 说明 |
|------|------|
| [nginx-spa-proxy.conf](nginx-spa-proxy.conf) | 微服务反向代理 + SPA（upstream 路由 + WebSocket 升级 + Docker DNS + gzip） |
| [nginx-spa-static.conf](nginx-spa-static.conf) | 纯静态 SPA 托管（try_files 回退 + 静态资源长缓存） |

## 🐧 Docker Compose

| 模板 | 说明 |
|------|------|
| [docker-compose.yml](docker-compose.yml) | 本地开发编排（MySQL + Redis 必选，Nacos / Kafka / Prometheus+Grafana 可选），全 healthcheck；应用服务在 IDE 中运行 |

## ⚙️ Spring Boot

| 模板 | 说明 |
|------|------|
| [application-microservice.yml](application-microservice.yml) | 微服务 application.yml（数据源 + Redis + Actuator + Prometheus，Dubbo/Nacos 和自研 RPC 可选段） |

## 🔑 环境变量

| 模板 | 说明 |
|------|------|
| [.env.example](.env.example) | .env 模板（MySQL + Redis + Nacos + AI 密钥 + COS + Vite 前端变量），按项目增减 |

## 📡 监控

| 模板 | 说明 |
|------|------|
| [prometheus-scrape.yml](prometheus-scrape.yml) | Prometheus 采集配置（Spring Boot Actuator 端点 + WSL/Docker Desktop 宿主机访问） |

## 🚀 CI/CD

| 模板 | 说明 |
|------|------|
| [deploy-template.yml](deploy-template.yml) | 单文件生产部署：双推 GHCR/ACR；Self-hosted Runner 优先拉取 GHCR，失败时回退 ACR，并生成 Spring Boot + MySQL/PostgreSQL + Redis 的生产 Compose |

### 部署模板约定

1. 将 `deploy-template.yml` 复制到新项目的 `.github/workflows/deploy.yml`。
2. 在 GitHub Actions 中配置以下公共凭据：
   - Variables：`ALIYUN_ACR_REGISTRY`、`ALIYUN_ACR_USERNAME`
   - Secret：`ALIYUN_ACR_PASSWORD`
3. 项目根目录默认提供 `Dockerfile`；生产 Compose 已内嵌在 workflow 中，无需项目额外维护。
4. 手动运行 workflow 时选择部署节点和生产数据库（MySQL 或 PostgreSQL）。应用容器固定注入 `APP_ENV=prod` 与 `SPRING_PROFILES_ACTIVE=prod`。

可选 Variables：

- `ALIYUN_ACR_IMAGE_NAME`：ACR 的 `命名空间/仓库`，默认 `wangshun_build/<GitHub仓库名>`。
- `DEPLOY_DOCKERFILE`：Dockerfile 路径，默认 `./Dockerfile`。
- `DATABASE_NAME`、`DATABASE_USERNAME`：生产数据库名称和业务账号，默认均为 `app`。
- `APP_PORT`：应用映射到宿主机的端口，默认 `8080`。

生产部署还需要 Secrets：`DATABASE_PASSWORD`、`DATABASE_ROOT_PASSWORD`（选择 MySQL 时必需）和 `REDIS_PASSWORD`。GHCR 镜像名自动使用 `${{ github.repository }}`，不需要额外配置账号、密码或镜像名。部署目标 `aliyun` / `wsl` 同时作为 self-hosted Runner 标签和 GitHub Environment 名称。

## ☁️ Cloudflare Workers

| 模板 | 说明 |
|------|------|
| [deploy-cloudflare-workers-template.yml](deploy-cloudflare-workers-template.yml) | 推送 main/master 自动部署 Worker：npm ci → typecheck/test（`--if-present`）→ `wrangler deploy`，可选部署后健康检查 |
| [wrangler-template.jsonc](wrangler-template.jsonc) | Worker `wrangler.jsonc` 配置模板（vars/密钥约定 + 自定义域名/KV/定时任务/队列可选段） |

### Workers 部署模板约定

1. 将 `wrangler-template.jsonc` 复制到项目根目录 `wrangler.jsonc`，替换 `<占位符>`；本地先跑通一次 `npx wrangler login && npx wrangler deploy` 完成 Worker 创建。
2. 在 GitHub Actions 中配置以下凭据：
   - Secret：`CLOUDFLARE_API_TOKEN`（Cloudflare → My Profile → API Tokens → 用 "Edit Cloudflare Workers" 模板创建）
3. 密钥不进 GitHub 也不进 `wrangler.jsonc`，用 `npx wrangler secret put <NAME>` 配置一次即可，跨部署持久，Actions 只负责推代码。
4. 健康检查与 monorepo 通过可选 Variables 配置：
   - `HEALTH_CHECK_URL`：部署后探活的 URL（如 `https://<name>.<子域>.workers.dev/health`），未配置则跳过。
   - `WORKER_DIRECTORY`：`wrangler.jsonc` 所在目录，默认 `.`。
   - `CLOUDFLARE_ACCOUNT_ID`：令牌可访问多个 Cloudflare 账号时必填（Dashboard 首页右侧可查）。

## 🕳️ FRP 内网穿透

| 模板 | 说明 |
|------|------|
| [frps-template.toml](frps-template.toml) | FRP 服务端配置（云服务器网关） |
| [frpc-template.toml](frpc-template.toml) | FRP 客户端配置（本地/WSL 边缘节点） |
| [frps-template.service](frps-template.service) | FRP 服务端 systemd 服务 |
| [frpc-template.service](frpc-template.service) | FRP 客户端 systemd 服务 |

## 🛠️ 开发脚本

| 模板 | 说明 |
|------|------|
| [local-dev-switch-template.sh](local-dev-switch-template.sh) | 本地开发环境切换脚本（环境变量默认值注入 + 冲突容器清理 + Docker Compose 启动） |
