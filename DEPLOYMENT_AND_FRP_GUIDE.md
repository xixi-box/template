# 部署与内网穿透模板：从代码到公网访问

本文不从 GitHub Actions、Docker 或 FRP 的功能列表讲起，而是从两个最基本的问题出发：

1. **怎样让指定版本的代码，稳定地运行在指定机器上？**——这是部署要解决的问题。
2. **怎样让公网用户，访问一台没有公网入口的机器？**——这是内网穿透要解决的问题。

部署负责“服务存在并运行”，内网穿透负责“流量能够到达服务”。它们不是一回事，也不能互相替代。

---

## 一、完整链路

以将应用部署到家中电脑、办公电脑或 WSL 为例，完整链路如下：

```text
代码提交
   │
   ▼
GitHub Actions 构建 Docker 镜像
   │
   ├── 推送到 GHCR
   └── 推送到阿里云 ACR
              │
              ▼
目标机器上的 Self-hosted Runner
   │  拉取本次提交对应的镜像
   ▼
Docker Compose 启动数据库、Redis 和应用
   │
   │ 应用监听宿主机端口，例如 8080
   ▼
FRP 客户端 frpc 主动连接公网服务器上的 frps
   │
   ▼
公网用户 → 公网服务器端口 → frps → 隧道 → frpc → 本地应用
```

从第一性原理看，这条链路只做了三次“确定性转换”：

- **源代码 → 不可变镜像**：解决“运行的到底是哪一版代码”。
- **镜像 → 正在运行的容器**：解决“代码怎样在目标机器运行”。
- **公网请求 → 内网服务端口**：解决“外部流量怎样抵达容器”。

---

## 二、部署模板解决什么

部署的本质不是把文件复制到服务器，而是让目标机器运行一个**身份明确、配置完整、可以重新获取的程序版本**。

当前 `deploy-template.yml` 把构建和部署分成两个任务。

### 1. 构建阶段：生产唯一版本的镜像

手动运行工作流时，需要选择：

- `target_env`：部署到带有 `aliyun` 或 `wsl` 标签的 Self-hosted Runner。
- `database`：生产环境使用 MySQL 或 PostgreSQL。

随后 GitHub 托管的 Runner 会：

1. 检出代码并检查 Dockerfile 与必要配置。
2. 使用本次工作流的临时 `github.token` 登录 GHCR。
3. 使用预先配置的账号密码登录阿里云 ACR。
4. 只构建一次 Docker 镜像。
5. 把同一个镜像同时推送到 GHCR 和 ACR。

每个仓库都会得到两个镜像标签：

- `${github.sha}`：精确对应一次 Git 提交，是部署真正使用的标签。
- `latest`：便于人工查看和临时使用，但不用于确定生产版本。

这里最重要的不是“双仓库”，而是 **SHA 标签使代码版本与运行镜像一一对应**。只使用 `latest` 会失去版本身份：同一个名字在不同时间可能代表完全不同的内容，排错和回滚都不可靠。

GHCR 与 ACR 的作用是镜像存储和分发。双推的意义是为不同网络条件提供两个下载来源，不是部署两套应用。

### 2. 部署阶段：让目标机器运行该版本

构建成功后，部署任务会被派发到匹配标签的 Self-hosted Runner。这个 Runner 就是实际运行应用的机器。

它会：

1. 临时登录 GHCR 和 ACR。
2. 优先拉取 GHCR 中带本次 SHA 的镜像；失败时改从 ACR 拉取同一个 SHA。
3. 在 `$HOME/deployments/<仓库名>` 生成生产用 `compose.yaml`。
4. 根据选择启动 MySQL 或 PostgreSQL，并启动 Redis。
5. 等待数据库和 Redis 通过健康检查。
6. 启动应用容器，并注入 `prod` 环境及数据库、Redis 配置。
7. 删除该项目的旧镜像，保留当前运行版本，避免磁盘持续膨胀。

生产 Compose 被内嵌在工作流中，原因很直接：对这些项目而言，生产部署结构是公共能力，而不是每个业务项目都应重复维护的一份文件。

### 3. 为什么同时使用 GHCR 和 ACR

当前策略是：

```text
构建时：GHCR 和 ACR 都必须推送成功
部署时：优先拉 GHCR，失败后拉 ACR
```

这抵御的是**部署节点访问某个镜像仓库失败**。它不能抵御构建阶段某个仓库不可写，因为模板要求两个仓库都成功接收镜像后才允许部署。这是有意采用的严格一致性策略：两个仓库中的同一 SHA 应当代表同一份构建产物。

### 4. 部署需要配置什么

GitHub Variables 用于非敏感配置：

| 名称 | 必需 | 作用 |
|---|---:|---|
| `ALIYUN_ACR_REGISTRY` | 是 | ACR Registry 地址 |
| `ALIYUN_ACR_USERNAME` | 是 | ACR 登录用户名 |
| `ALIYUN_ACR_IMAGE_NAME` | 否 | ACR 镜像路径，默认 `wangshun_build/<仓库名>` |
| `DEPLOY_DOCKERFILE` | 否 | Dockerfile 路径，默认 `./Dockerfile` |
| `DATABASE_NAME` | 否 | 业务数据库名，默认 `app` |
| `DATABASE_USERNAME` | 否 | 数据库业务账号，默认 `app` |
| `APP_PORT` | 否 | 应用映射到宿主机的端口，默认 `8080` |

GitHub Secrets 用于敏感信息：

| 名称 | 必需 | 作用 |
|---|---:|---|
| `ALIYUN_ACR_PASSWORD` | 是 | ACR 登录密码 |
| `DATABASE_PASSWORD` | 是 | 数据库业务账号密码 |
| `REDIS_PASSWORD` | 是 | Redis 密码 |
| `DATABASE_ROOT_PASSWORD` | 使用 MySQL 时 | MySQL root 密码 |

GHCR 不需要再配置用户名、密码或 `IMAGE_NAME`：

- 用户名使用触发工作流的 `github.actor`。
- 密码使用 GitHub 为任务签发的临时 `github.token`。
- 镜像名自动使用 `github.repository`，即 `<GitHub账号或组织>/<仓库名>`。

临时令牌每次任务重新签发是正常行为。它避免保存一份长期 GHCR 密码，但前提是工作流声明了正确的 `packages: write/read` 权限，包本身也允许该仓库访问。

---

## 三、FRP 内网穿透解决什么

内网机器通常可以主动访问公网，但公网无法主动连接内网机器，原因可能包括 NAT、动态 IP、运营商网络或防火墙。

FRP 利用这个不对称性：**由内网机器主动建立并维持一条到公网服务器的连接，然后让公网请求沿这条已建立的连接反向返回。**

因此 FRP 至少需要两个角色：

- `frps`：运行在有公网 IP 的服务器上，是公网入口。
- `frpc`：运行在应用所在的内网机器上，主动连接 `frps`。

### 1. frpc 和 frps 怎样互相认识

本质上，它们依靠三项信息建立关系：

```text
服务端公网地址 + FRP 通信端口 + 双方约定的 Token
```

当前模板中的对应关系是：

```toml
# frps.toml：在公网服务器等待连接
bindPort = 7000
auth.method = "token"
auth.token = "双方完全相同的长随机字符串"
```

```toml
# frpc.toml：知道去哪里连接，以及用什么凭据认证
serverAddr = "公网服务器 IP"
serverPort = 7000
auth.method = "token"
auth.token = "双方完全相同的长随机字符串"
```

完整过程可以拆成四步：

1. **发现服务端**：frpc 主动连接 `serverAddr:serverPort`，所以 frps 不需要提前知道内网机器的 IP。
2. **完成认证**：frpc 提交 Token，frps 与自己的 Token 比较；一致则接纳，不一致则拒绝。
3. **注册路由**：认证成功后，frpc 把 `name`、`type`、`remotePort` 等代理规则注册给 frps。
4. **保持连接**：frpc 持续维持连接。公网请求到达 `remotePort` 后，frps 沿已有连接把流量送回 frpc；连接中断后，frpc 会尝试重新连接。

例如客户端注册：

```toml
[[proxies]]
name = "my-app"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8080
remotePort = 18080
```

它表达的意思是：

> 请 frps 监听公网机器的 `18080` 端口，并把收到的流量通过 FRP 隧道转给这台内网机器的 `127.0.0.1:8080`。

对应的请求路径是：

```text
用户访问 公网IP:18080
        ↓
frps 根据 remotePort 找到 my-app
        ↓
通过已建立的连接把流量传给 frpc
        ↓
frpc 转发到 127.0.0.1:8080
```

其中：

- `7000` 是 frpc 与 frps 的内部通信端口。
- `18080` 这类 `remotePort` 是公网用户访问业务的端口。
- `name` 是代理规则的唯一标识，不是网络地址。
- 云服务器安全组和系统防火墙必须开放 `7000` 及实际使用的业务 `remotePort`。
- `transport.tls.enable = true` 用于加密 frpc 与 frps 之间的传输。
- 当前模板只启用了 TLS 和共享 Token。如果需要严格验证“对方确实是自己的 frps”，还应配置可信 CA、服务端证书和服务器名称校验。

一句话概括：**frpc 通过公网地址找到 frps，frps 通过共享 Token 接纳 frpc，再通过代理规则记住每条流量应该转发到哪里。**

### 2. 服务端 frps

`frps-template.toml` 当前定义：

- `7000`：frpc 与 frps 建立控制和数据连接的端口。
- Token 鉴权：只有持有相同 Token 的 frpc 才能接入。
- `7500`：服务端管理面板端口。
- TCP 多路复用：多个代理流量复用底层连接，减少重复建连成本。
- 日志保留三天。

`frps-template.service` 让 systemd 管理 frps：系统启动时启动，进程异常退出后等待五秒重启。

### 3. 客户端 frpc

`frpc-template.toml` 当前定义：

- 公网服务器 IP 和 `7000` 端口。
- 与 frps 完全相同的鉴权 Token。
- TLS 传输加密。
- 仅监听 `127.0.0.1:7400` 的本地管理面板。
- 三条 TCP 转发示例：本地 `80`、`3000`、`8888` 映射到公网服务器的同名端口。

一条代理规则可以理解为：

```text
公网服务器 remotePort
        ↓
       frps
        ↓ 已建立的 FRP 隧道
       frpc
        ↓
内网机器 localIP:localPort
```

例如，把 `localPort = 8080` 映射到 `remotePort = 18080`，公网用户访问 `公网IP:18080` 时，流量最终会抵达内网机器的 `127.0.0.1:8080`。

`frpc-template.service` 同样交给 systemd 守护。模板中的运行用户和文件路径是机器相关信息，安装时必须替换。

### 4. FRP 不做什么

FRP 不会：

- 构建或发布应用；
- 判断容器是不是健康；
- 自动给域名签发 HTTPS 证书；
- 修复应用、数据库或 Docker 故障；
- 代替访问控制和业务鉴权。

隧道在线只代表“路是通的”，不代表路尽头的应用是正常的。

---

## 四、两套模板怎样配合

如果选择部署到 `wsl`，典型流程是：

1. GitHub Actions 把新版本部署到 WSL 的 Docker 中。
2. 应用通过 `APP_PORT` 映射到 WSL 宿主机，例如 `127.0.0.1:8080`。
3. 常驻的 frpc 把这个本地端口注册到公网 frps。
4. 公网请求进入云服务器开放的 `remotePort`。
5. frps 通过隧道把流量交给 frpc。
6. frpc 再把流量送到应用端口。

每次发布通常只执行前两步。FRP 是长期运行的网络基础设施，不需要随每次应用发布重启；只要应用继续使用同一个宿主机端口，隧道路由就不需要变化。

如果选择直接部署到阿里云公网服务器，那么机器本身已经有公网入口，FRP 通常不是必要组件。此时可由防火墙、安全组和 Nginx 直接承接公网流量。判断标准不是“是否用了 Docker”，而是“目标应用是否缺少可控的公网入站路径”。

---

## 五、首次搭建与日常发布

### 首次搭建：只做一次

1. 在目标机器安装 Docker、Docker Compose 和 GitHub Self-hosted Runner。
2. 给 Runner 设置 `wsl` 或 `aliyun` 标签，并确保其运行账号有 Docker 权限。
3. 在 GitHub 配置 ACR、数据库和 Redis 所需的 Variables/Secrets。
4. 在公网服务器安装 frps，替换 Token、面板密码和实际路径，启用 systemd 服务。
5. 在内网机器安装 frpc，填写公网 IP、相同 Token、实际转发端口和实际路径，启用 systemd 服务。
6. 在云服务器安全组和系统防火墙中，仅开放确实需要的 FRP 通信端口和业务端口。
7. 分别验证容器本地可访问、frpc/frps 在线、公网端口可访问。

### 日常发布：每个版本执行

1. 提交并推送代码。
2. 手动运行 `Build and Deploy` 工作流。
3. 选择部署节点和数据库类型。
4. 等待构建、双仓库推送和目标节点部署完成。
5. 用公网入口验证应用版本和核心接口。

正常情况下，不需要手动登录服务器复制 JAR、修改生产 Compose、登录 GHCR，也不需要重启 FRP。

---

## 六、故障应该从哪里查

把系统按责任边界拆开，排错会非常直接：

| 现象 | 优先检查 |
|---|---|
| 镜像构建失败 | Dockerfile、构建上下文、GitHub Actions 日志 |
| ACR 登录或推送失败 | ACR Registry、用户名、密码、仓库权限 |
| GHCR 推送失败 | workflow 的 `packages: write` 权限、Package 访问关系 |
| 部署任务一直排队 | Self-hosted Runner 是否在线、标签是否匹配 |
| 数据库或 Redis 起不来 | Secrets、容器日志、数据卷和磁盘空间 |
| 本机端口可访问，公网不可访问 | frpc、frps、安全组、防火墙、remotePort |
| FRP 显示在线，但请求失败 | `localIP/localPort` 是否正确、应用是否监听该端口 |
| 公网能连但页面或接口异常 | 应用日志、Nginx 路由、业务配置；不是 FRP 本身 |

最便宜、最有效的验证顺序是从内到外：

```text
容器内服务
  → 宿主机本地端口
  → frpc 到 frps 的连接
  → 公网服务器端口
  → 域名 / HTTPS / 最终用户请求
```

哪一层第一次失败，问题通常就在这一层或它的直接上游。

---

## 七、安全底线

模板是结构，不是可以原样上线的凭据。实际部署至少要做到：

- 替换 FRP Token，使用足够长的随机值，并保证 frps/frpc 一致。
- 替换两个管理面板的默认账号密码。
- 不要把 frps 管理面板 `7500` 对整个公网开放；优先限制来源 IP、仅本机监听或通过安全通道访问。
- 只开放必要的业务 `remotePort`，不要长期把 MySQL、PostgreSQL、Redis 暴露到公网。
- 数据库、Redis、ACR 密码放在 GitHub Secrets，不写入仓库。
- 公网业务使用 HTTPS。FRP 的 TLS 保护 frpc 与 frps 之间的隧道，不自动等价于浏览器到公网入口的 HTTPS。
- 对外提供多个 Web 服务时，优先只穿透一个 Nginx/网关入口，再由它按域名或路径转发，减少公网端口和攻击面。

当前 `frpc-template.toml` 中的 `web-portfolio`、`svc-lumina-dashboard` 和 `svc-code-craft-gateway` 是具体项目示例，不是每个新项目都需要的公共规则。新项目应删除无关规则，只保留实际入口。`frps-template.toml` 和 `frpc-template.toml` 中的示例 Token、IP、面板密码也都必须替换。

---

## 八、一句话理解整套方案

**GitHub Actions 决定发布哪一版，镜像仓库负责保存这一版，Docker Compose 负责让这一版运行，FRP 负责让公网流量找到它。**

只要始终围绕这四个责任边界判断，就不会把部署问题误判成网络问题，也不会把隧道在线误认为应用已经健康。
