# 容器化生产部署手册

本文说明智库云在阿里云 ECS 上的镜像发布和人工上线流程。当前阶段不自动 SSH 到服务器部署；GitHub Actions 只构建并推送镜像，上线由运维人员在 ECS 执行。

## 架构与发布原则

- 宿主机 Nginx 继续作为 HTTPS 网关，保留现有证书和域名配置。
- 前端容器仅绑定 `127.0.0.1:3000`，后端容器仅绑定 `127.0.0.1:8000`，公网不直接开放这两个端口。
- Nginx 将页面请求转发至前端，将 API、健康检查和 `/video-notes` 转发至后端。
- 后端设置 `FORWARDED_ALLOW_IPS=*`，仅因为宿主机端口仅绑定 `127.0.0.1:8000`，公网请求只能经同机 Nginx 进入。该设置也会信任同一 Docker Compose 网络中的容器，因此不要把不受信任的服务接入 `zhiku-cloud` 网络，也不得把后端端口改成 `0.0.0.0:8000`；架构变化时应改为明确的代理 IP 范围。
- 每次生产发布必须使用已经通过 CI 的完整 40 位 Git commit SHA。`latest` 只用于人工浏览或临时排查，不用于生产 Compose 或部署脚本。
- 两个仓库的 `latest` 标签提升不具备原子性；生产环境始终以同一个精确 SHA 同时选择前后端镜像。

## 配置 ACR 和 GitHub

正式生产仍推荐阿里云容器镜像服务 **ACR 企业版**，实例地域固定为华北 2（北京）。ACR 个人版可作为此单机项目在资源受限或迁移期间的过渡选择，但阿里云官方将其定位为仅限开发测试且无 SLA 承诺，不能把它当作与企业版等价的生产保障；版本和 SLA 差异见[阿里云官方规格说明](https://help.aliyun.com/zh/acr/product-overview/differences-between-personal-edition-instances-and-enterprise-edition-instances)。无论选择企业版还是个人版，都要创建私有命名空间，并创建 `zhiku-backend`、`zhiku-frontend` 两个私有仓库。

**使用企业版时，两个企业版仓库都必须开启镜像版本不可变。** 分别进入 `zhiku-backend` 和 `zhiku-frontend` 的仓库管理页面，选择“基本信息 > 编辑 > 不可变”，确认两个仓库均已启用。操作路径和验证方法见[阿里云官方说明](https://help.aliyun.com/zh/acr/user-guide/turn-on-immutable-image-version)。未完成这一步不得启用企业版生产发布工作流。

个人版不提供仓库侧不可变保护，因此必须落实全部补偿控制：`Publish Images` 登录后先检查两个 SHA 标签，GitHub Actions 不会覆盖已存在的 SHA 标签，缺少哪个镜像才构建并推送哪个；两个镜像都存在后读取原始 OCI index，验证 `org.opencontainers.image.revision` 等于本次通过 CI 的 40 位 Git SHA，错误或缺失 annotation 会阻止发布。推送凭据仅供 GitHub Actions 使用，ECS 使用隔离的拉取专用凭据；禁止人工覆盖或删除任何 40 位 SHA 标签，服务器保留当前/上一镜像，生产不用 `latest`。企业版同样执行这些工作流与凭据控制，仓库不可变设置则是防止控制台或其他凭据绕过工作流覆盖标签的最终保护。工作流重新运行时可以修复单侧推送失败。

- GitHub Actions 使用推送专用凭据，仅允许向这两个仓库推送镜像。
- ECS 使用单独的拉取专用凭据，仅允许读取生产所需仓库，不能推送或删除镜像。

在 GitHub 仓库中配置以下 Actions Secrets：

- `ACR_REGISTRY`：GitHub Actions Secret 与 `deploy/.env.deploy` 均填写以下三种受支持的北京 ACR 公网地址之一：企业版 `your-instance-registry.cn-beijing.cr.aliyuncs.com`、新个人版 `crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com`，或旧个人版 `registry.cn-beijing.aliyuncs.com`。示例中的 `your-instance`、`crpi-your-instance` 等占位值必须替换为控制台显示的实际值。个人版独立域名的官方限制见[阿里云说明](https://help.aliyun.com/zh/acr/user-guide/individual-edition-instance-independent-domain-name-capacity-limit)。
- `ACR_USERNAME`：ACR 登录用户名
- `ACR_PASSWORD`：ACR 登录密码或专用访问凭据

再配置 Actions Variable：

- `ACR_NAMESPACE`：私有命名空间名称

为 `main` 启用分支保护，要求 `CI` 成功后才能合并。推送到 `main` 后，先观察 `CI`，再观察由它触发的 `Publish Images`。发布工作流只推送镜像，不自动 SSH，也不会直接修改 ECS。

## 首次初始化 ECS

先安装 Docker Engine、Docker Compose 2.30 或更高版本、Nginx 和 Python 3。`compose.production.yml` 使用 `env_file.format: raw`，以保证 SMTP 密码和 API Key 中的 `$` 保持原样；低于 2.30 的 Compose 不支持这一契约，部署、恢复和中断恢复脚本都会在任何运行时变更前拒绝执行。选择一个固定的部署账号；Docker 登录、发布和恢复必须使用同一账号，否则脚本读取不到该账号保存的 ACR 凭据。下面固定使用 root，不要在日常操作中混用其他账号：

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
scripts/recover-interrupted.sh
scripts/production-preflight.sh
scripts/inspect-restore-archive.py
```

将两个模板复制为宿主机配置。`deploy/.env.deploy` 填写北京 ACR 地址、命名空间和正式域名；`deploy/.env.production` 填写应用配置：

```bash
cd /opt/zhiku-cloud
cp deploy/.env.deploy.example deploy/.env.deploy
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.deploy deploy/.env.production
chmod 0640 scripts/production-preflight.sh
chmod 0750 scripts/deploy.sh scripts/restore-data.sh scripts/recover-interrupted.sh
chmod 0750 scripts/inspect-restore-archive.py
```

`deploy/.env.production` 至少要替换管理员邮箱、Fernet 加密密钥、SMTP 和 Google OAuth 占位值。其他模型供应商或 API Key 参考根目录 `.env.example` 按需加入。生产值和秘密始终留在宿主机；禁止提交到 Git、Dockerfile、Compose 文件或镜像层。

模板同时列出 SMTP 和 Google。至少配置一种登录方式；未启用的一组应删除对应 `REPLACE_*` 行或留空，不能把占位符带入生产文件。部署脚本会安全读取已知字段做生产预检，不会执行环境文件：它拒绝调试模式、不安全 Cookie、示例管理员、占位符、短加密密钥、部分填写的登录配置和错误的 Google 回调。未知的模型/API 配置会保留给应用使用，包含 `=` 的值也不会被截断。

使用 ECS 的拉取专用账号首次登录 ACR，密码通过标准输入提供，避免出现在 shell 历史中。新个人版不支持 ECS 免密拉取，必须显式执行 `docker login`；企业版和旧个人版也使用同一方式建立可审计的拉取凭据。以下示例占位值必须替换：

```bash
ACR_REGISTRY='crpi-your-instance.cn-beijing.personal.cr.aliyuncs.com'
read -rsp 'ACR pull password: ' ACR_PULL_PASSWORD && echo
printf '%s' "$ACR_PULL_PASSWORD" |
  docker login "$ACR_REGISTRY" --username 'YOUR_ECS_PULL_USERNAME' --password-stdin
unset ACR_PULL_PASSWORD
```

以后如果部署基础设施有变更，需要再次同步 `compose.production.yml`、`scripts/deploy.sh`、`scripts/restore-data.sh`、`scripts/recover-interrupted.sh`、`scripts/production-preflight.sh`、`scripts/inspect-restore-archive.py`、`deploy/nginx/zhiku-cloud.conf.example`、`.env.deploy.example` 和 `deploy/.env.production.example` 的结构变化。同步示例文件时不要覆盖服务器上的 `.env.deploy`、`.env.production` 或实际证书路径。

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

脚本会拉取前后端同一 SHA、停止后端、备份 `data`、依次启动并执行本机及公网健康检查。所有目标和回滚镜像拉取完成后、停止后端之前，脚本重新检查磁盘，要求备份所在文件系统的可用空间至少为当前 `data` 大小加 2 GiB；可通过 `ZHIKU_DEPLOY_DISK_RESERVE_BYTES` 提高预留量。备份先写入唯一的 `.partial` 文件，只有 `tar` 成功后才原子改名；失败时只删除该已知临时文件和已确认为空的本次备份目录。常用检查命令：

镜像拉取和停机前会先执行 `.env.production` 生产预检。至少一种登录方式必须完整可用：SMTP 需要 `SMTP_HOST`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_FROM`，Google 需要 client ID、secret 和规范域名的 HTTPS callback。预检失败不会调用 Docker，也不会改变当前服务。

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

脚本会先取得与发布相同的 `deploy.lock`，再通过 `production-preflight.sh` 执行与发布完全相同的只读生产预检；受支持的北京 ACR 公网地址、Compose raw 值、Fernet、Cookie、管理员和登录配置任一无效时，不会展开归档、创建事务 marker 或停止后端。它拒绝备份目录之外的路径、符号链接、危险归档成员，以及超过成员数或解压总量限制的归档；默认解压总量上限为 20 GiB，可通过 `ZHIKU_RESTORE_MAX_MEMBERS`、`ZHIKU_RESTORE_MAX_BYTES` 调低或在评估后调整。真正解压前，可用空间必须至少为归档展开大小加 2 GiB；可用 `ZHIKU_RESTORE_DISK_RESERVE_BYTES` 提高预留量。停机前脚本会验证应用 SQLite 的完整性及核心表，并验证 `chroma_db/chroma.sqlite3` 的完整性和非空 schema。随后脚本停止后端，把原数据保存在权限受限且名称唯一的 `data.safety.*` 安全副本中，切换已验证数据，并使用 `current-version` 中的精确 SHA 和 `--pull never` 重启。只有本机和公网健康检查都成功，恢复才算完成。

交换开始后若复制、移动、启动、健康检查失败，或收到 HUP、INT、TERM，脚本会先停止后端、恢复安全副本，再决定是否重启原 SHA。若旧数据无法确认已经回到活动路径，后端会保持停止，脚本会打印旧数据、失败数据和活动目录的精确人工恢复路径。生产数据变更前会原子写入 `deploy/transaction`；只有发布、恢复或自动回退完整成功后才删除。未进入数据交换的失败只清理本次已知 `data.restore.*` 暂存目录；交换开始后的暂存、安全副本和失败数据会保留以便审计。整个流程不删除 Compose volume，也不批量清理 Docker 数据。

## 断电或强制终止后的恢复

主机启动后、任何发布或数据恢复前，先检查事务标记：

```bash
cd /opt/zhiku-cloud
test ! -e deploy/transaction || ./scripts/recover-interrupted.sh
```

`deploy.sh` 和 `restore-data.sh` 发现已有 `deploy/transaction` 会拒绝继续并指向该命令。恢复脚本取得同一个锁，严格解析 marker，不执行其中内容；对于中断发布，它恢复精确的旧 SHA 和原版本记录；对于中断数据恢复，它根据 marker 阶段以及活动 `data`、`data.restore.*` 和 `data.safety.*` 的实际状态处理交换前、两次重命名之间、新数据已生效和回滚后重启再次失败的现场。回滚会先原子记录 `rollback_started`，确认旧数据恢复后再记录 `rollback_ready`；只有后者可重入 active-only 现场。无法无歧义恢复时，后端保持停止，marker 与精确目录路径会保留，禁止删除后直接重跑。

## 备份保留与磁盘监控

- ECS 本地只保留最新 10 份已确认完整的发布备份；至少一份满足业务恢复点要求的长期备份必须加密复制到 OSS 或另一台主机，形成异机副本。
- 每次发布前和每日监控 `df -h /opt/zhiku-cloud`、`du -sh /opt/zhiku-cloud/{data,backups,logs}`。可用空间低于“当前数据大小 + 2 GiB”时先停止发布并扩容或清理。
- 仅在确认没有 `deploy/transaction`、没有发布或恢复进程、异机副本可用且目标归档不再需要后，按完整备份目录逐个删除第 11 份及更旧备份。不要使用通配符删除 `data`、`data.safety.*` 或未知暂存目录。
- `data.safety.*` 不是普通轮换备份。恢复成功并完成业务验收后才能手工删除对应安全副本；失败现场必须保留到故障关闭。

## 故障排查

- **ACR 拉取失败**：确认 ECS 已登录北京 ACR、仓库为私有但账号有 pull 权限、`ACR_REGISTRY`/`ACR_NAMESPACE` 正确，并确认目标 SHA 标签在两个仓库都存在。
- **本机健康检查失败**：查看 `docker compose ... ps` 与 `logs`，检查 `.env.production`、容器健康状态以及 `/opt/zhiku-cloud/data`、`logs` 对容器用户可写。
- **公网健康检查失败**：先确认 `127.0.0.1:3000` 和 `127.0.0.1:8000` 正常，再执行 `nginx -t`，检查 Nginx 日志、DNS A 记录、HTTPS 证书和安全组。
- **笔记或视频接口 404**：确认 Nginx 后端正则包含 `/video-notes`，并已重载最新配置。
- **上传失败或超时**：核对 `client_max_body_size`、代理读写超时、磁盘空间以及 `data`/`logs` 写权限。

生产发布不依赖 `latest`，不使用自动 SSH 部署，也不把任何生产秘密同步回开发机或 Git 仓库。
