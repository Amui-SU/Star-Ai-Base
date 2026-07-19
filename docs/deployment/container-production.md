# 容器化生产部署手册

本文说明智库云在阿里云 ECS 上的镜像发布和人工上线流程。当前阶段不自动 SSH 到服务器部署；GitHub Actions 只构建并推送镜像，上线由运维人员在 ECS 执行。

## 架构与发布原则

- 宿主机 Nginx 继续作为 HTTPS 网关，保留现有证书和域名配置。
- 前端容器仅绑定 `127.0.0.1:3000`，后端容器仅绑定 `127.0.0.1:8000`，公网不直接开放这两个端口。
- Nginx 将页面请求转发至前端，将 API、健康检查和 `/video-notes` 转发至后端。
- 后端设置 `FORWARDED_ALLOW_IPS=*`，仅因为端口仅绑定 `127.0.0.1:8000`，所有转发请求只能来自同机 Nginx。不得把后端端口改成 `0.0.0.0:8000`，否则任意客户端都可能伪造转发头。
- 每次生产发布必须使用已经通过 CI 的完整 40 位 Git commit SHA。`latest` 只用于人工浏览或临时排查，不用于生产 Compose 或部署脚本。
- 两个仓库的 `latest` 标签提升不具备原子性；生产环境始终以同一个精确 SHA 同时选择前后端镜像。

## 配置 ACR 和 GitHub

在阿里云容器镜像服务 ACR 的北京地域创建一个私有命名空间，并创建 `zhiku-backend`、`zhiku-frontend` 两个私有仓库。不要使用阿里云主账号凭据，并严格分开两类身份：

- GitHub Actions 使用推送专用凭据，仅允许向这两个仓库推送镜像。
- ECS 使用单独的拉取专用凭据，仅允许读取生产所需仓库，不能推送或删除镜像。

在 GitHub 仓库中配置以下 Actions Secrets：

- `ACR_REGISTRY`：例如 `registry.cn-beijing.aliyuncs.com`
- `ACR_USERNAME`：ACR 登录用户名
- `ACR_PASSWORD`：ACR 登录密码或专用访问凭据

再配置 Actions Variable：

- `ACR_NAMESPACE`：私有命名空间名称

为 `main` 启用分支保护，要求 `CI` 成功后才能合并。推送到 `main` 后，先观察 `CI`，再观察由它触发的 `Publish Images`。发布工作流只推送镜像，不自动 SSH，也不会直接修改 ECS。

## 首次初始化 ECS

先安装 Docker Engine、Docker Compose 插件、Nginx 和 Python 3。选择一个固定的部署账号；Docker 登录、发布和恢复必须使用同一账号，否则脚本读取不到该账号保存的 ACR 凭据。下面固定使用 root，不要在日常操作中混用其他账号：

```bash
sudo -i
install -d -m 0750 /opt/zhiku-cloud /opt/zhiku-cloud/scripts
install -d -m 0700 /opt/zhiku-cloud/{deploy,data,logs,backups}
cd /opt/zhiku-cloud
```

从仓库的同一已审核提交复制这些部署基础设施文件到服务器：

```text
compose.production.yml
deploy/.env.deploy.example
deploy/.env.production.example
deploy/nginx/zhiku-cloud.conf.example
scripts/deploy.sh
scripts/restore-data.sh
```

将两个模板复制为宿主机配置。`deploy/.env.deploy` 填写北京 ACR 地址、命名空间和正式域名；`deploy/.env.production` 填写应用配置：

```bash
cd /opt/zhiku-cloud
cp deploy/.env.deploy.example deploy/.env.deploy
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.deploy deploy/.env.production
chmod 0750 scripts/deploy.sh scripts/restore-data.sh
```

`deploy/.env.production` 至少要替换管理员邮箱、Fernet 加密密钥、SMTP 和 Google OAuth 占位值。其他模型供应商或 API Key 参考根目录 `.env.example` 按需加入。生产值和秘密始终留在宿主机；禁止提交到 Git、Dockerfile、Compose 文件或镜像层。

使用 ECS 的拉取专用账号首次登录 ACR，密码通过标准输入提供，避免出现在 shell 历史中：

```bash
read -rsp 'ACR pull-only password: ' ACR_PULL_PASSWORD && echo
printf '%s' "$ACR_PULL_PASSWORD" | docker login registry.cn-beijing.aliyuncs.com --username 'YOUR_ECS_PULL_ONLY_USERNAME' --password-stdin
unset ACR_PULL_PASSWORD
```

以后如果部署基础设施有变更，需要再次同步 `compose.production.yml`、`scripts/deploy.sh`、`scripts/restore-data.sh`、`deploy/nginx/zhiku-cloud.conf.example`、`.env.deploy.example` 和 `deploy/.env.production.example` 的结构变化。同步示例文件时不要覆盖服务器上的 `.env.deploy`、`.env.production` 或实际证书路径。

## 合并 Nginx 配置

参考 `deploy/nginx/zhiku-cloud.conf.example`，把内容合并到 ECS 当前站点配置，而不是直接覆盖整份配置。`limit_req_zone` 必须位于 Nginx 的 `http {}` 上下文；保留服务器上已经生效的 `ssl_certificate` 和 `ssl_certificate_key` 实际路径。

示例会公开 `/docs`、`/redoc` 和 `/openapi.json` API 文档端点。若生产环境不需要公开接口文档，应在 Nginx 中删除这些前缀，或增加认证/IP 白名单；该决定不影响应用健康检查和发布脚本。`www` 的 HTTPS server 只做 301 跳转，证书仍必须同时覆盖 `zhiku-cloud.cn` 与 `www.zhiku-cloud.cn`。

确认安全组只对公网开放 80、443 和必要的运维端口，不开放 3000、8000。验证并平滑重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 发布精确 SHA

从成功的 `Publish Images` 运行或 GitHub commit 页面取得完整 40 位小写 SHA，例如：

```bash
cd /opt/zhiku-cloud
./scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567
```

脚本会拉取前后端同一 SHA、停止后端、备份 `data`、依次启动并执行本机及公网健康检查。常用检查命令：

```bash
cd /opt/zhiku-cloud
export IMAGE_TAG="$(tr -d '[:space:]' < deploy/current-version)"
docker compose --project-name zhiku-cloud --env-file deploy/.env.deploy -f compose.production.yml ps
docker compose --project-name zhiku-cloud --env-file deploy/.env.deploy -f compose.production.yml logs --tail=200 backend frontend
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:3000/
curl --fail https://zhiku-cloud.cn/health
```

## 镜像回滚

部署失败时脚本会尝试恢复旧镜像。需要人工回滚时，读取 `previous-version` 并再次调用同一个脚本：

```bash
cd /opt/zhiku-cloud
ROLLBACK_SHA=$(tr -d '[:space:]' < deploy/previous-version)
./scripts/deploy.sh "$ROLLBACK_SHA"
```

镜像回滚不会恢复数据。部署脚本为每次变更创建备份，但自动恢复只处理容器镜像和版本记录，避免在故障处理中悄悄覆盖用户数据。

## 恢复数据备份

不要手工解包或搬移生产数据。确认要恢复的归档后，只使用受控脚本，并传入 `/opt/zhiku-cloud/backups` 下的归档绝对路径：

```bash
cd /opt/zhiku-cloud
./scripts/restore-data.sh /opt/zhiku-cloud/backups/REPLACE_WITH_BACKUP/data.tar.gz
```

脚本会使用与发布相同的 `deploy.lock`，拒绝备份目录之外的路径、符号链接和危险归档成员；它会在停机前解包并检查非空 SQLite 数据库与 Chroma 内容。随后脚本停止后端，把原数据保存在权限受限且名称唯一的 `data.safety.*` 安全副本中，切换已验证数据，并使用 `current-version` 中的精确 SHA 和 `--pull never` 重启。只有本机和公网健康检查都成功，恢复才算完成。

交换开始后若复制、移动、启动、健康检查失败，或收到 HUP、INT、TERM，脚本会保留失败数据、恢复安全副本并重启原 SHA 后端。操作结束后检查脚本打印的安全副本路径；确认数据正常前不要删除它。整个流程不删除 Compose volume，也不批量清理 Docker 数据。

## 故障排查

- **ACR 拉取失败**：确认 ECS 已登录北京 ACR、仓库为私有但账号有 pull 权限、`ACR_REGISTRY`/`ACR_NAMESPACE` 正确，并确认目标 SHA 标签在两个仓库都存在。
- **本机健康检查失败**：查看 `docker compose ... ps` 与 `logs`，检查 `.env.production`、容器健康状态以及 `/opt/zhiku-cloud/data`、`logs` 对容器用户可写。
- **公网健康检查失败**：先确认 `127.0.0.1:3000` 和 `127.0.0.1:8000` 正常，再执行 `nginx -t`，检查 Nginx 日志、DNS A 记录、HTTPS 证书和安全组。
- **笔记或视频接口 404**：确认 Nginx 后端正则包含 `/video-notes`，并已重载最新配置。
- **上传失败或超时**：核对 `client_max_body_size`、代理读写超时、磁盘空间以及 `data`/`logs` 写权限。

生产发布不依赖 `latest`，不使用自动 SSH 部署，也不把任何生产秘密同步回开发机或 Git 仓库。
