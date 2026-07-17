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
| [docker-compose.dev.yml](docker-compose.dev.yml) | 本地开发环境（MySQL + Redis 必选，Nacos / Kafka / Prometheus+Grafana 可选），全 healthcheck |

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
| [deploy-template.yml](deploy-template.yml) | GitHub Actions 双推 GHCR/ACR；Self-hosted Runner 默认拉取 GHCR，失败时回退 ACR，并使用 IaC Compose 分阶段启动 |

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
