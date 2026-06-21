# 收藏夹知识库-bilibili版块

将 B 站收藏夹里的访谈、演讲、课程与技术视频，沉淀为**可语义检索、可追溯来源、可对话**的本地知识库。

**仓库**：[Amui-SU/Amui-SU-Star-Ai-Base](https://github.com/Amui-SU/Amui-SU-Star-Ai-Base)

---

## 目录

- [收藏夹知识库-bilibili版块](#收藏夹知识库-bilibili版块)
  - [目录](#目录)
  - [核心价值](#核心价值)
  - [功能一览](#功能一览)
  - [技术栈](#技术栈)
  - [系统要求](#系统要求)
  - [快速开始](#快速开始)
    - [Windows（推荐：仓库内置启动器）](#windows推荐仓库内置启动器)
    - [Windows：启动器补充](#windows启动器补充)
    - [手动安装（全平台）](#手动安装全平台)
  - [环境变量](#环境变量)
    - [应用与存储](#应用与存储)
    - [LLM 路由](#llm-路由)
    - [DashScope（默认对话 / Embedding / ASR）](#dashscope默认对话--embedding--asr)
    - [其他可选提供方（与 `LLM_PROVIDER` 对应）](#其他可选提供方与-llm_provider-对应)
  - [启动与访问地址](#启动与访问地址)
  - [多模型提供方](#多模型提供方)
  - [工作流程](#工作流程)
  - [目录结构](#目录结构)
  - [OpenClaw Skill](#openclaw-skill)
  - [测试与诊断脚本](#测试与诊断脚本)
  - [ASR 与音频兜底](#asr-与音频兜底)
  - [费用说明](#费用说明)
  - [相关文档](#相关文档)
  - [常见问题](#常见问题)
  - [免责声明](#免责声明)
  - [License](#license)
  - [路线图](#路线图)

---

## 核心价值

| 能力           | 说明                                                        |
| -------------- | ----------------------------------------------------------- |
| **自动入库**   | 从收藏夹拉取视频元数据，获取可转写内容，切块后写入向量库    |
| **语义检索**   | 基于 ChromaDB 的向量检索，按语义召回相关片段                |
| **RAG 问答**   | 结合检索上下文由大模型生成回答，并尽量附带视频来源          |
| **本地持久化** | SQLite 存业务数据，Chroma 存向量；数据默认在项目 `data/` 下 |

适用场景：学习视频复盘、公开课整理、技术分享归档、个人「第二大脑」式收藏夹运营等。

---

## 功能一览

- **系统账号 + 内容源绑定**：使用邮箱账号登录，登录后扫码绑定 B 站账号读取收藏夹列表与视频。
- **收藏夹与视频**：列表、分页、全量预览；支持默认收藏夹整理预览与执行（后端接口 + 前端入口）。
- **知识库构建**：按工作区/知识库隔离同步收藏夹、构建/更新向量、查询进度与统计。
- **对话与检索**：在当前知识库内流式/非流式问答、纯检索片段；支持收藏夹/视频提问范围和多种 LLM 提供方切换（见下文）。
- **移动端体验**：手机端默认进入沉浸式聊天界面，需要管理资料、切换主题或账号时可展开侧栏。
- **ASR**：对接 DashScope 语音转写；直链不可用时走本地下载 + ffmpeg + 上传识别兜底。
- **OpenClaw**：内置 `skills/bilibili-rag-local`，可把本地 API 暴露给 OpenClaw 调用。

---

## 技术栈

| 层级 | 选型                                             | 说明                 |
| ---- | ------------------------------------------------ | -------------------- |
| 后端 | FastAPI、Uvicorn、SQLAlchemy 2.x、aiosqlite      | 异步 SQLite          |
| AI   | LangChain、OpenAI 兼容客户端、DashScope          | 对话、Embedding、ASR |
| 向量 | ChromaDB                                         | 持久化目录可配置     |
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS 4 | 默认端口 3000        |
| 其他 | loguru、httpx、pydantic-settings                 | 日志与配置           |

---

## 系统要求

- **Python** 3.11+（推荐与 `setup_dependencies.ps1` 中 winget 目标版本一致）
- **Node.js** LTS（用于前端）
- **ffmpeg** 已加入 `PATH`（ASR 本地兜底强烈依赖）

---

## 快速开始

### Windows（推荐：仓库内置启动器）

在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 install
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 logs
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 stop
```

启动器会统一选择 Python，安装依赖到同一环境，启动后端和前端，并把日志写入 `logs/`。运行状态保存在 `logs/runtime.json`；停止时只停止本项目进程，避免误停其它本地服务。

**双击运行（不手敲命令）**：在资源管理器中双击仓库根目录下的这些脚本：

- `安装依赖.bat`
- `启动.bat`
- `停止.bat`
- `状态.bat`
- `日志.bat`

---

<a id="windows-one-click-extras"></a>

### Windows：启动器补充

仓库内置的 `scripts\dev.ps1` 与根目录 BAT 是 Windows 主流程，适合团队协作和新克隆仓库使用。旧的外层 `.bat` / `.vbs` 脚本属于本机便利脚本，不随仓库分发；若你的工作区仍保留这些历史脚本，可以继续按需自用，但建议优先迁移到仓库内置的 `安装依赖.bat`、`启动.bat`、`停止.bat`、`状态.bat` 和 `日志.bat`。

如需指定 Python，可将用户环境变量 **`BILIBILI_RAG_PYTHON`** 设置为目标 `python.exe` 的完整路径，再运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 install
```

### 手动安装（全平台）

**0）ffmpeg**

- Windows：安装后将 `ffmpeg.exe` 所在目录加入 `PATH`
- macOS：`brew install ffmpeg`
- Linux：使用发行版包管理器安装 `ffmpeg`

**1）Python 依赖**

```bash
pip install -r requirements.txt
```

**2）前端依赖**

```bash
cd frontend
npm install
```

**3）环境变量**

在项目根目录新建 `.env`（或 `.env.local`），至少配置你实际使用的模型与 ASR 所需密钥，见下一节。

---

## 环境变量

配置从 **环境变量** 或项目根目录的 **`.env` / `.env.local`** 读取（`extra="ignore"`，未列出的键可安全忽略）。

### 应用与存储

| 变量                       | 默认值                                       | 说明                       |
| -------------------------- | -------------------------------------------- | -------------------------- |
| `APP_HOST`                 | `0.0.0.0`                                    | 后端监听地址               |
| `APP_PORT`                 | `8000`                                       | 后端端口                   |
| `DEBUG`                    | `true`                                       | 调试模式（影响日志级别等） |
| `DATABASE_URL`             | `sqlite+aiosqlite:///./data/bilibili_rag.db` | 异步 SQLite 连接串         |
| `CHROMA_PERSIST_DIRECTORY` | `./data/chroma_db`                           | Chroma 持久化目录          |

### LLM 路由

| 变量           | 默认值      | 说明                                                   |
| -------------- | ----------- | ------------------------------------------------------ |
| `LLM_PROVIDER` | `dashscope` | 当前对话使用的提供方，见 [多模型提供方](#多模型提供方) |

### DashScope（默认对话 / Embedding / ASR）

| 变量                 | 默认值                                  | 说明                                              |
| -------------------- | --------------------------------------- | ------------------------------------------------- |
| `DASHSCOPE_API_KEY`  | 空                                      | 必填之一：对话与 ASR 常用                         |
| `OPENAI_BASE_URL`    | `https://api.openai.com/v1`             | DashScope 兼容调用时常改为阿里云文档中的 base URL |
| `LLM_MODEL`          | `gpt-4-turbo`                           | 对话模型名（以 DashScope 侧为准）                 |
| `EMBEDDING_MODEL`    | `text-embedding-3-small`                | 向量模型                                          |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com/api/v1` | ASR 等 DashScope API                              |
| `ASR_MODEL`          | `paraformer-v2`                         | 线上 ASR 模型                                     |
| `ASR_MODEL_LOCAL`    | `paraformer-realtime-v2`                | 本地兜底相关                                      |
| `ASR_TIMEOUT`        | `600`                                   | ASR 超时（秒）                                    |
| `ASR_INPUT_FORMAT`   | `pcm`                                   | ASR 输入格式                                      |

### 其他可选提供方（与 `LLM_PROVIDER` 对应）

按需填写对应 `*_API_KEY`、`*_BASE_URL`、`*_MODEL`：

- **DeepSeek**：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`
- **OpenAI**：`OPENAI_NATIVE_API_KEY`、`OPENAI_NATIVE_BASE_URL`、`OPENAI_NATIVE_MODEL`
- **Kimi（Moonshot）**：`KIMI_API_KEY`、`KIMI_BASE_URL`、`KIMI_MODEL`
- **SiliconFlow**：`SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL`、`SILICONFLOW_MODEL`
- **智谱 GLM**：`ZHIPU_API_KEY`、`ZHIPU_BASE_URL`、`ZHIPU_MODEL`

---

## 启动与访问地址

**后端**（在项目根目录）：

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

或使用配置中的 host/port：

```bash
python -m uvicorn app.main:app --reload
```

| 地址                                                         | 说明             |
| ------------------------------------------------------------ | ---------------- |
| [http://localhost:8000/docs](http://localhost:8000/docs)     | Swagger API 文档 |
| [http://localhost:8000/health](http://localhost:8000/health) | 健康检查         |

**前端**：

```bash
cd frontend
npm run dev
```

| 地址                                           | 说明                                    |
| ---------------------------------------------- | --------------------------------------- |
| [http://localhost:3000](http://localhost:3000) | Web 界面（需与后端 CORS、接口地址一致） |

生产构建：

```bash
cd frontend
npm run build
npm run start
```

---

## 多模型提供方

后端支持的 `LLM_PROVIDER` 取值与界面展示名称如下（可在前端切换，部分配置也可通过 API 持久化到 `.env`）：

| `LLM_PROVIDER` | 说明             |
| -------------- | ---------------- |
| `dashscope`    | 阿里云 DashScope |
| `deepseek`     | DeepSeek         |
| `openai`       | OpenAI           |
| `kimi`         | Moonshot Kimi    |
| `siliconflow`  | SiliconFlow      |
| `zhipu`        | 智谱 GLM         |

Embedding 与 ASR 仍以项目当前实现为准（默认与 DashScope 体系配合）；切换对话模型时请确认对应 Key 与 Base URL 已正确配置。

---

## 工作流程

1. **登录**：B 站扫码，建立会话。
2. **选收藏夹**：查看列表与视频，可选整理默认收藏夹。
3. **同步与构建**：同步收藏夹变更，对新增/更新项拉取内容、ASR、切块、写入向量库。
4. **使用**：语义检索或 RAG 问答，回答中尽量引用来源视频。手机端可直接提问，按需展开侧栏管理资料或账号。

---

## 目录结构

```
.
├── app/                      # FastAPI 后端
│   ├── main.py               # 应用入口、路由挂载、CORS
│   ├── config.py             # pydantic-settings 配置
│   ├── database.py           # 异步 DB 会话
│   ├── models.py             # ORM / Pydantic 模型
│   └── routers/              # auth / favorites / knowledge / chat
├── frontend/                 # Next.js 前端
├── data/                     # 运行时生成：SQLite、Chroma（勿提交敏感库）
├── logs/                     # 运行时日志
├── docs/                     # 功能大纲、前端优化说明等
├── scripts/
│   └── dev.ps1               # Windows 开发启动器
├── skills/
│   └── bilibili-rag-local/   # OpenClaw Skill
├── tests/                    # 自动化测试与诊断脚本（见下文运行方式）
├── requirements.txt
├── setup_dependencies.ps1
├── setup_dependencies.bat
├── start.bat
├── stop.bat
├── status.bat
├── logs.bat
└── README.md
```

---

## OpenClaw Skill

本仓库提供 **`skills/bilibili-rag-local/SKILL.md`**，用于把本地运行的服务接入 OpenClaw。

**前置条件**

1. 本地已按上文启动后端，可打开 `http://127.0.0.1:8000/docs`。
2. OpenClaw 已安装并能加载本地 Skills。

**接入步骤**

1. 将 `skills/bilibili-rag-local` 复制到 OpenClaw 的 Skills 目录（例如 `~/.openclaw/skills/`）。
2. 重启或刷新 OpenClaw 的 Skills 列表。
3. 通过 Skill 调用 scoped 接口，例如 `POST /knowledge-bases/{id}/chat`、`POST /knowledge-bases/{id}/search`、`GET /knowledge-bases/{id}/stats`。旧全局 `/chat/ask|ask/stream|search` 与 `/knowledge/*` RAG/知识库入口已返回 `410 Gone`。

**建议**：先完成收藏夹入库再高频问答；问题越具体，召回通常越稳定。

---

## 测试与诊断脚本

`tests/` 下脚本依赖项目根目录的模块与配置，请**在项目根目录**执行，例如：

```bash
# 在仓库根目录
python tests/debug_asr_single.py
python tests/diagnose_rag.py
python tests/sync_cache_vectors.py
```

| 脚本                    | 用途                     |
| ----------------------- | ------------------------ |
| `debug_asr_single.py`   | 验证单个视频音频链路     |
| `diagnose_rag.py`       | 检查向量检索召回         |
| `sync_cache_vectors.py` | 将数据库缓存与向量库对齐 |

---

## ASR 与音频兜底

部分 B 站音频直链存在 **403 / 过期 / 区域限制**，无法被云端直接拉取。此时会尝试：

1. 使用登录态在本地下载音频；
2. 用 **ffmpeg** 转为 16 kHz 单声道等格式；
3. 上传至 DashScope 完成识别。

因此 **ffmpeg 必须在 PATH 中**，否则兜底路径会失败。

---

## 费用说明

使用 DashScope / 其他云 API 时，可能产生：

- 对话 Token（LLM）
- 向量 Embedding Token
- ASR 按时长计费

建议：先用**短时长视频**打通流程并观察账单；正式批量入库前评估收藏夹规模与模型单价。

---

## 相关文档

| 文档                                                                 | 内容                             |
| -------------------------------------------------------------------- | -------------------------------- |
| [docs/功能大纲.md](docs/功能大纲.md)                                 | 功能模块、接口索引、用户路径说明 |
| [docs/frontend-ui-optimization.md](docs/frontend-ui-optimization.md) | 前端交互与 UI 优化记录           |

---

## 常见问题

**Q：为什么有的音频能转写、有的报错或很慢？**  
A：直链可用时走在线链路；不可用则走本地下载 + ffmpeg，步骤更多且受网络与文件大小影响。

**Q：向量检索为空？**  
A：确认已完成对应收藏夹的「构建」流程；检查 `CHROMA_PERSIST_DIRECTORY` 与 `data/` 是否可写。

**Q：前端连不上后端？**  
A：确认后端已启动、端口一致；开发环境下后端 CORS 当前为宽松配置，若仍失败请检查浏览器控制台与接口基地址。

**Q：没有 `.env.example`？**  
A：请直接参考本文 [环境变量](#环境变量) 在根目录创建 `.env` 或 `.env.local`。

**Q：启动器提示缺依赖，或用的不是我想用的 Python？**
A：先运行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 doctor` 查看诊断，再运行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 install` 或双击 **`setup_dependencies.bat`** 安装依赖。若系统里有多个 Python，可在用户环境变量中设置 **`BILIBILI_RAG_PYTHON`** 为目标解释器完整路径。

---

## 免责声明

本项目仅供**个人学习与技术研究**。使用者须自行遵守 B 站及第三方平台的服务条款与适用法律法规，**不得用于未授权的商业用途或侵权行为**。

---

## License

MIT（见仓库内 [LICENSE](LICENSE) 文件）。

---

## 路线图

- [ ] 对话历史与会话管理、检索历史记录
- [ ] 支持 B 站分 P 视频
- [ ] 适配更多 Embedding / 向量后端与开源模型

欢迎通过 [Issues](https://github.com/Amui-SU/Amui-SU-Star-Ai-Base/issues) 反馈问题与需求。
