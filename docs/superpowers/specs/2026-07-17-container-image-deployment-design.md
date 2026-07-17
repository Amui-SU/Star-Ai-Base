# 智库云容器镜像发布设计

## 目标

将本地开发到阿里云 ECS 的发布流程收敛为：本地提交代码，GitHub Actions 完成测试、构建并推送镜像，服务器通过一条命令拉取并部署指定版本。运行数据、日志和生产密钥始终保留在服务器，不进入 Git 或镜像。

第一阶段采用“CI 自动构建镜像，服务器手动执行发布脚本”；稳定运行后可在不改变镜像和 Compose 结构的前提下，增加 GitHub Actions SSH 自动发布。

## 已有基础

- 后端为 FastAPI，监听 8000 端口，已有 `Dockerfile.backend`。
- 前端为 Next.js 16 静态导出，已有 `frontend/Dockerfile`，构建产物由 Nginx 容器在 80 端口提供。
- 已有 `docker-compose.yml`，但它同时承担本地构建和运行职责，不适合作为生产发布文件。
- 已有 GitHub Actions CI，能够执行后端测试、前端测试、Lint 和前端构建。
- 服务器已有域名、HTTPS 和宿主机 Nginx，因此首期保留现有网关，避免迁移证书和备案站点配置。

## 方案选择

### 采用方案

使用 GitHub Actions 构建两个不可变镜像并推送到阿里云 ACR，北京 ECS 使用生产 Compose 文件按 Git 提交 SHA 拉取镜像。发布由服务器本地脚本完成，并包含数据备份、健康检查和失败回滚。

### 未采用方案

- 服务器 `git pull` 后本地构建：操作简单，但占用 ECS CPU、内存和磁盘，构建慢且环境重复。
- 直接同步源码或 `frontend/out`：速度快但缺乏完整版本边界，后端依赖和系统包容易漂移，回滚也不完整。
- 首期将宿主机 Nginx 和证书容器化：最终形态更统一，但会扩大上线风险，当前收益不足。

## 架构

生产环境保留三层：

1. 宿主机 Nginx 监听 80/443，负责 HTTPS、真实客户端 IP、限流和路径反向代理。
2. `frontend` 容器仅绑定 `127.0.0.1:3000:80`，提供 Next.js 静态导出内容。
3. `backend` 容器仅绑定 `127.0.0.1:8000:8000`，提供 FastAPI 接口。

宿主机 Nginx将页面请求代理到 3000，将后端 API 路径（包括 `/video-notes`）代理到 8000。容器端口不直接暴露到公网。

## 镜像与版本

每次 `main` 分支 CI 通过后构建：

- `<acr>/zhiku-cloud/frontend:<full-git-sha>`
- `<acr>/zhiku-cloud/backend:<full-git-sha>`
- 同一镜像额外更新 `:latest`，仅用于人工查看，不作为生产部署依据。

生产 Compose 使用 `IMAGE_TAG` 选择具体 Git SHA。回滚通过恢复上一个成功部署的 SHA 完成，不依赖重新构建。

基础镜像继续使用固定主版本，后续可进一步固定到 digest。GitHub Actions 中第三方 Action 应固定到完整提交 SHA，避免标签漂移。

## 前端构建配置

`NEXT_PUBLIC_API_URL` 属于浏览器端构建参数，必须在构建镜像时写入，不能只在容器启动时提供。生产值为 `https://zhiku-cloud.cn`。

`frontend/Dockerfile` 增加构建参数，并在执行 `npm run build` 前暴露为环境变量。CI 构建前端镜像时显式传入生产地址。本地 Compose 可继续使用本地地址或相对地址，不与生产配置混用。

## 配置与密钥

生产服务器保存 `/opt/zhiku-cloud/.env.production`，权限设置为仅部署用户可读。该文件包含 SMTP、OAuth、管理员邮箱、加密密钥和模型服务配置，不提交 Git、不复制进镜像，也不存入 GitHub Actions。

GitHub Secrets 只保存构建和发布基础设施凭据：

- `ACR_REGISTRY`
- `ACR_USERNAME`
- `ACR_PASSWORD`

第二阶段自动部署时再增加服务器地址、部署用户名和专用 SSH 私钥。SSH 用户只获得执行部署所需的最小权限。

## 持久化与备份

服务器目录固定为：

- `/opt/zhiku-cloud/data`：SQLite 和 Chroma 数据。
- `/opt/zhiku-cloud/logs`：应用日志。
- `/opt/zhiku-cloud/backups`：部署前备份。
- `/opt/zhiku-cloud/deploy`：生产 Compose、环境文件和发布状态。

后端容器将 `data` 和 `logs` 绑定挂载到 `/app/data` 与 `/app/logs`。部署脚本更新容器前，先停止会写 SQLite 的后端或执行 SQLite 在线备份，再备份数据库文件；Chroma 数据与数据库应使用同一发布前快照批次。备份失败时终止部署。

镜像更新和容器重建不得删除上述宿主机目录。发布脚本禁止对数据卷执行 `docker compose down -v`。

## 发布流程

### CI 阶段

1. 检出提交。
2. 执行现有后端测试、前端测试、Lint 和前端生产构建。
3. 仅当检查全部通过时登录 ACR。
4. 使用 BuildKit 缓存分别构建前端和后端镜像。
5. 推送 Git SHA 标签和 `latest` 标签。
6. 输出镜像 digest，便于审计。

### 服务器阶段

部署脚本接收一个完整 Git SHA：

1. 校验 SHA 格式、生产环境文件和持久化目录。
2. 记录当前成功版本。
3. 创建数据备份。
4. 登录 ACR 并拉取目标前后端镜像。
5. 使用 `IMAGE_TAG=<sha> docker compose -f compose.production.yml up -d` 更新服务。
6. 等待后端 `/health` 和前端 HTTP 健康检查通过。
7. 从宿主机通过 HTTPS 检查 `https://zhiku-cloud.cn`。
8. 全部通过后写入当前成功版本；失败则恢复上一个 SHA 并再次健康检查。

部署期间宿主机 Nginx保持运行。前端更新可能有短暂连接切换；当前单机规模不引入蓝绿双实例。

## 健康检查与日志

后端健康检查请求容器内 `http://127.0.0.1:8000/health`。前端健康检查请求容器内首页。生产 Compose 使用 `depends_on.condition: service_healthy` 让依赖关系可观察，但发布脚本仍执行独立的外部检查，确保域名、HTTPS 和宿主机 Nginx链路也正常。

Compose 为容器日志配置轮转，限制单文件大小和保留数量，避免填满系统盘。应用自身文件日志继续写入宿主机 `logs` 目录。

## 回滚

每次成功部署将 SHA 写入 `/opt/zhiku-cloud/deploy/current-version`，部署前复制为 `previous-version`。自动回滚只切换镜像版本，不默认恢复数据。

如果新版本执行了不可逆数据迁移，必须在发布说明中标记，并在人工确认后决定是否恢复同批次数据备份。本项目当前使用启动时兼容迁移逻辑，实施阶段仍需验证旧镜像读取新数据的兼容性。

## 安全边界

- 8000 和 3000 只监听回环地址。
- ACR 仓库使用私有仓库，服务器使用专用拉取凭据。
- 应用密钥不进入镜像层、Compose 文件、GitHub 日志或仓库。
- 宿主机 Nginx继续承担验证码接口限流，并传递可信的真实客户端 IP。
- 部署脚本输出时屏蔽密码、Token 和完整环境变量。

## 实施范围

需要新增或修改：

- 调整 `frontend/Dockerfile`，支持生产 API 构建参数和健康检查。
- 调整 `Dockerfile.backend`，增加健康检查所需能力并优化镜像缓存。
- 新增 `compose.production.yml`，只引用 ACR 镜像，不在服务器构建。
- 新增 `scripts/deploy.sh`，实现校验、备份、部署、检查和回滚。
- 新增 `.github/workflows/publish-images.yml`，在 CI 通过后发布镜像。
- 更新 `.env.example` 和部署文档，但不写入真实密钥。
- 保留现有 `docker-compose.yml` 作为本地开发入口。

## 验收标准

- 本地推送 `main` 后，CI 检查通过才会产生两个同 SHA 镜像。
- ECS 不需要 Git、Node.js 或 Python 即可部署新版本，只需要 Docker、Compose 和 Nginx。
- 数据库、Chroma、日志和 `.env.production` 在容器重建后保持不变。
- 前后端只可通过宿主机回环端口访问，公网仅开放 80/443。
- 发布脚本能够部署指定 SHA，健康检查失败时自动恢复上一成功镜像。
- 能够从 Git 提交 SHA 追踪到镜像 digest 和服务器当前版本。
- 强制刷新浏览器后，前端调用 `https://zhiku-cloud.cn` 的后端接口，视频笔记接口不返回 Nginx 静态 404。

## 非目标

- 首期不引入 Kubernetes、Docker Swarm 或多服务器编排。
- 首期不迁移现有 SQLite/Chroma 到托管数据库或对象存储。
- 首期不容器化宿主机 Nginx、Certbot 和证书。
- 首期不自动执行生产部署，待至少完成三次人工一键发布和一次回滚演练后再启用。
