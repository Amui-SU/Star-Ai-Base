# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

B 站收藏夹知识库 — 将 B 站收藏夹视频自动拉取、ASR 转写、向量化，提供语义检索和 RAG 问答。本地持久化（SQLite + ChromaDB），前端 Next.js + 后端 FastAPI。已支持多用户体系（系统账号 + 工作区 + 知识库隔离）。

## 常用命令

### Windows 启动器

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor   # 环境诊断
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 install  # 安装依赖
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 start    # 启动前后端
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 stop     # 停止
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 status   # 状态查看
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 logs     # 查看日志
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 restart  # 重启
```

或双击根目录 `.bat` 包装器：`启动.bat`、`停止.bat`、`状态.bat`、`日志.bat`、`安装依赖.bat`

可用环境变量 `BILIBILI_RAG_PYTHON` 指定 Python 解释器路径。启动器将 Python 选择、进程归属判断、端口检测等逻辑集中在 `scripts/dev.ps1`，通过 `logs/runtime.json` 跟踪运行进程，停止时只杀本项目进程（按命令行路径精准匹配，不按端口粗暴杀）。

### 手动启动

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

### 测试

```bash
pytest tests/ -v
# 重点测试：test_system_auth / test_source_bindings / test_knowledge_scope /
# test_knowledge_scope_filters / test_knowledge_base_scoping
```

诊断脚本（在项目根目录运行）：
- `python tests/debug_asr_single.py` — 验证单个视频音频链路
- `python tests/diagnose_rag.py` — 检查向量检索召回
- `python tests/sync_cache_vectors.py` — 对齐数据库缓存与向量库

## 架构

### 层级结构

```
app/
├── main.py           # FastAPI 入口，lifespan，CORS，路由注册
├── config.py         # pydantic-settings，读取 .env/.env.local，多 LLM 提供方配置
├── database.py       # 异步 SQLAlchemy 引擎 + 会话工厂（aiosqlite）
├── models.py         # ORM 模型 + Pydantic 请求/响应模型
├── security.py       # bcrypt 密码哈希、session token (SHA-256)、Fernet 加密（开发环境用稳定派生 key）
├── dependencies.py   # get_current_user / get_current_workspace / get_knowledge_base_for_user
├── routers/
│   ├── auth.py           # B 站扫码登录（QR → poll → session 持久化到 user_sessions）
│   ├── system_auth.py    # 系统用户注册/登录/登出/me（HttpOnly cookie 会话，14天过期）
│   ├── chat.py           # 核心对话（智能路由 + 流式 + 6 种 LLM 提供方切换）
│   ├── knowledge.py      # 知识库构建/同步/统计/清空（旧 B 站 session_id 驱动）
│   ├── knowledge_bases.py# 多用户知识库 CRUD + scoped search/chat/chat-stream/build/delete/scope-options
│   ├── favorites.py      # 收藏夹列表/视频/整理/清理
│   ├── imports.py        # 多来源导入入口：B 站视频 URL 已接入，抖音/通用 URL 预留
│   └── source_bindings.py# B 站账号绑定到 workspace（QR 绑定流程 + 凭据加密存储 + 自定义视频名）
└── services/
    ├── bilibili.py       # B 站 API（登录/收藏夹/视频/音频/WBI 签名）
    ├── rag.py            # ChromaDB + DashScopeEmbeddings + 分块 + 检索 + scoped search
    ├── content_fetcher.py# 内容获取：ASR → 基本信息 二级降级
    ├── asr.py            # DashScope ASR（Transcription 在线 + Recognition 本地兜底）
    └── wbi.py            # B 站 WBI 签名
```

### 多用户数据模型

```
SystemUser → Workspace (1:1 via WorkspaceMember) → KnowledgeBase (1:N)
  └── SourceBinding (B站账号) → SourceCredential (Fernet 加密存储 Cookie)
  └── SystemSession (HttpOnly cookie, SHA-256 hashed token)
  └── IngestionTask (知识库构建/单条导入任务状态)
  └── VideoTitleOverride (按 workspace + knowledge_base + source_binding + bvid 覆盖视频显示名)
```

注册时自动创建 Workspace + WorkspaceMember（role=owner）。所有新接口通过 `dependencies.py` 做三层校验：当前用户 → 当前工作区 → 知识库归属。

### API 体系

| 层级 | 旧接口（session_id 驱动） | 主路径（系统用户 + workspace 隔离） |
|------|--------------------------|-----------------------------------|
| 认证 | `/auth/qrcode` + `/auth/session/{id}` | `/system-auth/register|login|logout|me|me/display-name` |
| 知识库/RAG | `/knowledge/*`、`/chat/ask|ask/stream|search` 已返回 `410 Gone` | `/knowledge-bases/{id}/search|chat|chat/stream|build|build/status|stats|scope-options` |
| 绑定 | — | `/source-bindings` + `/source-bindings/bilibili/qrcode` |
| 收藏夹 | `/favorites/*` | `/source-bindings/{id}/favorites` + `/source-bindings/{id}/favorites/{media_id}/videos` |
| 导入 | — | `/imports/methods` + `/imports/url` |
| 视频名 | — | `/source-bindings/{id}/videos/title` |
| 本地连接 | — | `/local-connection/lan-address`、`/local-connection/mobile-connect`、`/local-connection/mobile-connect.png` |

旧的全局知识库/RAG 接口已禁用，统一提示迁移到 `/knowledge-bases/*` scoped API。前端主流程只走 `systemAuthApi/sourceBindingApi/knowledgeBaseApi/importApi`；`authApi/favoritesApi/knowledgeApi/chatApi` 仅作为历史封装保留，不应接入新业务。

### 关键设计决策

**智能路由**（`chat.py` `_prepare_messages`）：LLM 路由优先（direct/db_list/db_content/vector），失败降级规则路由。`direct` — 闲聊；`db_list` — 清单只用标题；`db_content` — 总结用全量数据库内容；`vector` — 语义检索后 RAG。

**多 LLM 提供方**：`chat.py` `PROVIDER_META` 管理 6 种（dashscope/deepseek/openai/kimi/siliconflow/zhipu），运行时可通过 API 切换，配置持久化到 `.env.local`。切换后重置 `knowledge.py` 全局 `_rag_service`。

**Embedding**：`rag.py` 优先 `DashScopeEmbeddings`，导入失败回退 `OpenAIEmbeddings`。

**ASR 双路径**：先 HEAD 探测音频 URL 可达性 → 可达走 Transcription（异步提交+轮询），不可达走本地下载 → ffmpeg 转码 PCM → Recognition 直传。长音频自动切分（默认 1200 秒/段）。

**RAG 范围隔离**：`VideoCache` 已从全局 `bvid` 唯一改为 `workspace_id + knowledge_base_id + source_binding_id + bvid` 作用域缓存。`add_video_content()` 写入时带 `workspace_id/knowledge_base_id/source_binding_id` 元数据；`search_in_knowledge_base()` 强制 `$and` 过滤，指定提问范围时追加 `bvid IN (...)`。重建/导入单个视频时调用 `delete_video_in_knowledge_base()` 只删除当前知识库内的向量，并会检测缺失 scoped 向量后用缓存内容补建。

**提问范围**：`KnowledgeBaseChatRequest` 支持 `folder_ids` 与 `bvids`。`/knowledge-bases/{id}/scope-options` 返回当前知识库可提问的收藏夹和视频；前端 `ChatScopePicker` 可在整个知识库、收藏夹、单个视频之间切换，最终仍走 scoped chat/chat-stream。

**导入体系**：`imports.py` 提供一级导入入口。`/imports/methods` 返回 B 站收藏夹、视频 URL、抖音、通用 URL 等方式；当前已实现 B 站视频 URL 导入，写入 `VideoCache`、`FavoriteFolder("单条视频导入")`、`FavoriteVideo`、`IngestionTask` 并同步向量。B 站收藏夹扫码绑定仍作为第二层级入口复用 `source_bindings.py`。

**自定义视频名**：`VideoTitleOverride` 以 workspace + knowledge_base + source_binding + bvid 为唯一作用域保存自定义标题。`source_bindings.py` 在返回收藏夹视频时合并 `custom_title/display_title/original_title`，`/source-bindings/{id}/videos/title` 负责创建、更新和清除覆盖名。

**账号资料**：`/system-auth/me/display-name` 支持登录后修改显示名，前端 `UserMenu` 负责编辑态、保存、恢复和登出。

**管理员用户管理**：`ADMIN_EMAILS` 可用英文逗号配置管理员邮箱；为空时系统中首个注册用户自动拥有管理员权限。管理员接口集中在 `/system-auth/admin/users`：列表、启用/禁用、重置临时密码。禁用用户会删除该用户所有系统会话；重置密码也会删除旧会话并把用户状态恢复为 `active`。前端入口在 `UserMenu`，只有 `SystemUserResponse.is_admin=true` 且传入 `onOpenAdmin` 时显示“用户管理”，面板组件为 `AdminUsersPanel.tsx`。不要在前端绕过权限判断，后端仍必须以 `_get_current_admin_user()` 为准。

**模型状态**：`/chat/llm/config`、`/chat/llm/provider-config`、`/chat/health/llm` 均需要系统登录态。配置接口返回当前与可用 provider，健康检查返回可用性、模型和延迟；前端模型选择展示头像和延迟，展开后可切换 provider 或进入配置。

**手机端本地连接**：`routers/local_connection.py` 负责检测真实局域网 IPv4（只接受 `10.*`、`172.16-31.*`、`192.168.*`，忽略 `198.18.*` 代理网段和 `169.254.*` 链路本地地址），返回电脑端 API 地址、连接页、PNG 二维码地址和内联 `qr_data_url`。二维码内容为 `zhikuyun://connect?api=...`，`_qr_png_bytes()` 与 `_qr_data_url()` 使用 `lru_cache(maxsize=64)` 缓存，避免用户菜单 Copy 后重新生成导致弹窗慢。`/mobile-connect.png` 保留给旧客户端/浏览器图片访问，并带 `Cache-Control: public, max-age=86400`。

**局域网 CORS / PNA**：`main.py` 的 CORS 允许 localhost、私有 IPv4、`capacitor://localhost`、`ionic://localhost`。另有 `allow_private_network_preflight` 中间件，当请求带 `Access-Control-Request-Private-Network: true` 时返回 `Access-Control-Allow-Private-Network: true`，用于兼容手机 WebView/Chrome 的 Private Network Access 预检。

**APK 原生 HTTP 兜底**：`frontend/lib/nativeHttp.ts` 封装 `requestWithNativeFallback()`。普通 Web 优先使用 `fetch`；Capacitor 原生壳中如果 `fetch` 抛错，会退到 `CapacitorHttp.request()`。`frontend/capacitor.config.ts` 必须保持 `plugins.CapacitorHttp.enabled = true`，Android Manifest 必须保留 `INTERNET`、`CAMERA`、cleartext HTTP 和 `zhikuyun://connect` deep link。公网 HTTPS 部署并移除本地连接时，主要删除 `LocalConnectionBootstrap`、`LocalConnectionSettings`、`localConnection*`、`nativeHttp`、`local_connection.py` 以及 UserMenu 的局域网地址区块。

**进程管理**（`scripts/dev.ps1`）：`Test-ProjectProcess` 按命令行完整路径+分隔符精准匹配，避免 substring 误杀。失败清理直接停 `Start-Process` 返回的子进程 PID。`stop` 优先读 `runtime.json` 的 PID，再用 `Get-CimInstance` 扫描并按 `Test-ProjectProcess` 过滤。

### 前端

Next.js 16 App Router，单页应用。

**组件：**
- `AuthPage.tsx` — 系统登录/注册全屏页，右侧卡片内嵌检索流程动画演示（替代旧欢迎页）
- `UserMenu.tsx` — 右上角用户头像下拉（头像、显示名、邮箱、电脑局域网地址/二维码、编辑用户名、登出）
- `AdminUsersPanel.tsx` — 管理员用户管理弹层（查看账号、启用/禁用、重置临时密码；自账号操作禁用）
- `LocalConnectionBootstrap.tsx` / `LocalConnectionSettings.tsx` — APK 本地连接入口。Bootstrap 处理 `zhikuyun://connect?api=...` deep link 和启动 query；Settings 负责手动填写、扫码、测试并保存后端地址。
- `KnowledgeBasePanel.tsx` — 侧栏知识库下拉切换/创建/选择/删除（含确认提示）
- `ChatPanel.tsx` — 对话区（已移除 legacy 回退，只走 scoped API；模型头像+延迟；支持知识库/收藏夹/视频提问范围）
- `ChatScopePicker.tsx` — 聊天输入区的提问范围选择器，消费 `scope-options`
- `SourcesPanel.tsx` — 收藏夹资料管理（已迁移到 source_binding_id + knowledgeBaseId；支持入库、整理、清理、自定义视频名）
- `ImportModal.tsx` — 多来源导入弹窗，B 站视频 URL 已接入，收藏夹扫码绑定作为二级入口
- `ThinkingProcess.tsx` — 模型原生 thinking/reasoning 流式展示与折叠
- `DevIndicatorGuard.tsx` — 本地隐藏 Next dev indicator

**移动端 UI 约定：**
- `app/page.tsx` 的根容器会根据侧边栏状态添加 `app-shell sidebar-open/sidebar-closed`。移动端默认收起侧边栏；收起时隐藏 `workspace-topbar`，展开侧边栏时才显示顶部栏，用于主题切换和 `UserMenu`。
- 移动端工作台样式集中在 `app/globals.css` 末尾的 `Mobile chat shell refinements` 覆盖段。该段负责去掉移动端外框/阴影、锁定 `100dvh`、隐藏横向溢出、让侧栏使用实色背景，并隐藏本地 Next devtools/toast 宿主（`nextjs-portal`、`[data-nextjs-dev-overlay]`、`[data-nextjs-toast]`）。
- `ChatPanel` 的发送按钮必须使用独立的 `composer-send-button` 样式，不要重新复用 `mode-chip` / `mode-chip-send`。`mode-chip` 只服务提问范围等胶囊控件；发送按钮是圆形图标按钮（发送态上箭头、生成中停止图标）。
- 空对话态通过 `.empty-state` 在移动端占满聊天可用高度并轻微低于视觉中心；调整位置时优先改移动端覆盖段里的 `transform`，避免用过大的 `padding-top` 制造滚动条。

**状态流：**
```
[加载中] → me() → 未登录 → AuthPage(登录/注册)
                → 已登录 → 工作台
                   ├─ 侧栏 KnowledgeBasePanel(下拉切换/创建/删除)
                   ├─ SourcesPanel(收藏夹资料/导入/入库/整理/视频名)
                   ├─ ImportModal(多来源导入；B站收藏夹绑定为二级入口)
                   ├─ ChatPanel(选KB→scoped API + ChatScopePicker / 不选→禁用输入提示选择知识库)
                   └─ UserMenu(头像+改名+登出)
```

`lib/api.ts` 仍保留历史 API 客户端定义，但登录后页面以 `systemAuthApi.me()` 判断登录态，并通过 `sourceBindingApi/knowledgeBaseApi/importApi` 访问内容源、知识库、导入与聊天能力；不再依赖旧 `bili_session`。

**手机端连接测试重点**：后端覆盖 `tests/test_local_connection.py`；前端覆盖 `frontend/lib/localConnection.test.ts`、`frontend/lib/localConnectionScanner.test.ts`、`frontend/lib/nativeHttp.test.ts`、`frontend/components/LocalConnectionSettings.test.tsx`、`frontend/components/UserMenu.test.tsx`、`frontend/lib/api.test.ts`。改动 APK 连接能力时至少运行这些测试，并检查 `frontend/android/app/src/main/assets/capacitor.config.json` 内仍有 `webDir: out` 和 `CapacitorHttp.enabled: true`，且没有 `server.url`。

## 多用户演进进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段 1 | 系统账号 + 工作区 | ✅ 完成 |
| 阶段 2 | B 站账号外部绑定 | ✅ 完成 |
| 阶段 3 | 知识库数据归属 + SourcesPanel 迁移 | ✅ 完成 |
| 阶段 4 | 向量库隔离 + scoped 删除 | ✅ 完成 |
| 阶段 5 | 任务持久化 | ✅ IngestionTask 模型 + build → DB 持久化 + 状态查询已迁移 |
| 阶段 5.5 | 登录后工作台交互优化 | ✅ 知识库下拉、收藏夹资料、导入、多范围提问、模型状态、自定义视频名 |
| 阶段 6 | 服务层重构 | ⬜ 未开始 |

## 开发/生产模式切换

当前 `.env.local` 中 `DEBUG=true`（本地开发模式）。切换到生产模式时需修改：

```env
DEBUG=false

# 必配（生产）：
APP_ENCRYPTION_KEY=<Fernet.generate_key() 生成的值>  # 凭据加密密钥，开发模式自动派生
SMTP_HOST=smtp.qq.com                                 # 邮件发送，开发模式跳过
SMTP_PORT=587
SMTP_USER=your_email@qq.com
SMTP_PASSWORD=授权码

# 按需（生产）：
HTTP_PROXY=http://127.0.0.1:7890                      # Google OAuth 后端回调需要（国内访问 Google API）
CORS 锁定域名                                          # main.py 中 allow_origins
Alembic 初始化                                         # 替换 Base.metadata.create_all
login_sessions → Redis                                 # 当前内存字典，多进程不共享
```

**开发模式自动跳过**：SMTP 邮件（验证码直接返回）、Fernet 加密（SHA-256 派生开发密钥）、CORS 宽松。

## 当前限制与注意事项

- **旧全局知识库/RAG 接口已禁用**：`/knowledge/*` 与 `/chat/ask|ask/stream|search` 返回 `410 Gone`，新业务必须使用 `/knowledge-bases/*`
- **旧向量数据不自动清空**：缺失 scoped 向量时依赖 DB fallback 和后续重建补齐，不建议无备份清空 ChromaDB
- **前端完全迁移**：SourcesPanel + ChatPanel 均走 scoped API，`bili_session` 已从 page.tsx 移除
- **`login_sessions` 内存字典**（已加 TTL 清理）：生产需换 Redis
- **Google OAuth state**：HMAC 签名自包含 token，无状态多 worker 安全。已知限制：state 未绑定用户会话（RFC 6819 §3.6），生产需加固
- **`_ip_rate_limit` 内存字典**：验证码 IP 限流，多 worker 不共享，生产需换 Redis 或网关层限流
- **bcrypt 4.0.1 固定**：bcrypt 5.x 与 passlib 1.7.4 不兼容，不要升级
