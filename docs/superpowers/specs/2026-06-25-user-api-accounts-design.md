# 用户自带 AI 服务密钥管理设计

## 目标

将智库云统一设计为多用户 Web 应用。无论用户把它部署在本机、内网服务器，还是线上服务器，正式产品路径都以“用户自带 AI 服务密钥”为主：谁使用 AI 能力，谁配置自己的第三方 API Key。

同时预留“官方 / 个人”模型来源切换：`个人` 使用用户自带 Key；`官方` 未来接平台付费通道，现阶段先复用管理员全局模型配置作为占位。现阶段不做平台代付费，不做套餐扣费，只预留调用记录和未来平台 API 池的扩展点。

## 结论

- 不再单独设计“本地部署模式”和“线上 Web 模式”。
- 本地部署只是用户自己运行这套 Web 应用，权限与 AI 服务密钥逻辑不分叉。
- `.env.local` 中的全局 API Key 保留为开发、兼容、管理员排障和未来官方付费通道占位。
- 普通用户不能写全局 API 配置；是否使用官方通道由用户自己的 `llm_api_source` 显式记录。
- 用户选择 `个人` 且没有配置 AI 服务密钥时，聊天、摘要、复盘、联网搜索等 AI 能力应提示先添加 AI 服务密钥。
- 用户选择 `官方` 且全局模型 Key 缺失时，返回 `official_api_required`，前端显示官方通道未开通。

## 配置

新增轻量配置：

```env
API_ACCOUNT_MODE=user_required
PLATFORM_API_ENABLED=false
BILLING_ENABLED=false
```

含义：

- `API_ACCOUNT_MODE=user_required`：所有普通用户必须使用自己的 AI 服务密钥。
- `PLATFORM_API_ENABLED=false`：平台付费 API 通道暂不启用；官方来源只作为管理员全局模型配置的占位入口。
- `BILLING_ENABLED=false`：不启用余额、套餐、扣费。

未来收费时可以扩展为：

```env
API_ACCOUNT_MODE=hybrid
PLATFORM_API_ENABLED=true
BILLING_ENABLED=true
```

## 数据模型

### user_api_accounts

保存用户自己的第三方 AI 服务密钥。

字段建议：

- `id`
- `user_id`
- `provider`
- `display_name`
- `api_key_encrypted`
- `base_url`
- `model`
- `thinking_config`
- `enabled`
- `is_default`
- `last_validated_at`
- `last_error`
- `created_at`
- `updated_at`

约束：

- 同一用户可以保存多个 provider。
- 同一用户同一 provider 只能有一个默认密钥。
- API Key 使用现有 `APP_ENCRYPTION_KEY` 加密保存。
- 后端接口永远不返回明文 API Key。

### usage_events

预留未来计费与审计，现在只记录调用量。

字段建议：

- `id`
- `user_id`
- `api_account_id`
- `api_source`，现阶段为 `personal` 或 `official`
- `feature`，例如 `chat`、`summary`、`web_search`
- `provider`
- `model`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `estimated_cost`
- `status`
- `error_code`
- `created_at`

### platform_api_accounts

未来平台付费 API 池使用，现阶段不实现业务入口，只保留设计位置。上线用户自带 API 前不需要建表也可以。

### system_users.llm_api_source

保存用户当前模型来源偏好。

- `personal`：使用用户自己的 AI 服务密钥。
- `official`：使用官方通道；现阶段映射到管理员全局模型配置，未来接平台 API 池和计费。
- 空值：兼容旧用户，优先展示已有个人账号；没有个人账号但有全局模型 Key 时展示官方来源。

## 后端边界

新增服务层 `ApiCredentialResolver`，所有 AI 调用都通过它取凭证。

输入：

- 当前用户
- feature
- provider，可选
- model，可选

输出：

- `api_source`
- `provider`
- `api_key`
- `base_url`
- `model`
- `thinking_config`
- `account_id`

现阶段解析规则：

1. 读取当前用户 `llm_api_source`。
2. 来源为 `personal` 时，读取当前用户默认 AI 服务密钥；如果请求指定 provider，则读取该 provider 对应的用户账号。
3. 来源为 `official` 时，读取管理员全局模型配置；没有全局 Key 时返回 `official_api_required`。
4. 来源为空时用于兼容旧用户：优先使用个人账号；没有个人账号但存在全局模型 Key 时使用官方来源。
5. 所有结果写入 `usage_events.api_source`，个人账号写入 `api_account_id`，官方来源的 `api_account_id` 为空。

管理员全局配置接口继续保留管理员权限，普通用户只能选择是否使用官方来源，不能写入官方配置。

## API 接口

新增用户账号接口：

```text
GET    /api-accounts
POST   /api-accounts
PATCH  /api-accounts/{id}
DELETE /api-accounts/{id}
POST   /api-accounts/{id}/validate
POST   /api-accounts/{id}/set-default
```

新增模型来源接口：

```text
POST   /chat/llm/source
```

`GET /chat/llm/config` 返回 `current_api_source`，每个 provider 返回 `official_enabled`、`personal_enabled` 和当前来源下的 `enabled`。

返回内容只包含：

- provider
- display_name
- base_url
- model
- enabled
- is_default
- configured
- last_validated_at
- last_error

不返回 API Key 明文。

## 前端体验

新增入口：

- 用户菜单：`AI 服务密钥`
- 模型选择弹窗顶部：`官方 / 个人`
- 聊天区空状态：当前来源为个人且没有可用模型时显示 `先添加 AI 服务密钥`
- 模型选择弹窗：显示当前来源下可用的 provider；官方未开通显示 `未开通`，个人未配置显示 `未配置`
- 当前来源有可用模型时，聊天页不再显示“未配置”提示

普通用户不再看到“配置全局模型”或“配置全局 Tavily Key”的入口。

管理员入口保留：

- 用户管理
- 全局模型配置，标注为开发/兼容配置
- 未来平台 API 池，等 `PLATFORM_API_ENABLED=true` 后再开放

## 调用流程

聊天：

```text
用户提问
-> ApiCredentialResolver 根据 llm_api_source 获取个人密钥或官方配置
-> 创建 LLM 客户端
-> 流式回答
-> 写入 usage_events
```

联网搜索：

```text
用户开启 Tavily
-> 检查当前用户是否有 Tavily 服务密钥
-> 没有则提示添加 Tavily 服务密钥
-> 有则使用用户 Tavily Key
-> 写入 usage_events
```

## 错误处理

- 未配置 AI 服务密钥：返回稳定错误码 `api_account_required`。
- 官方通道未开通：返回稳定错误码 `official_api_required`。
- API Key 验证失败：记录到 `last_error`，前端提示用户更新账号。
- API 服务限流或余额不足：透出 provider、密钥名称和简短错误，不暴露密钥。
- `APP_ENCRYPTION_KEY` 缺失：生产环境禁止保存 API Key。

## 测试策略

后端：

- 普通用户可以新增、编辑、删除自己的 AI 服务密钥。
- 用户不能读取或修改其他用户的 AI 服务密钥。
- API Key 不在响应体中返回。
- 没有 AI 服务密钥时聊天返回 `api_account_required`。
- 有默认密钥时聊天使用该用户密钥。
- 切换到官方来源且全局 Key 存在时，聊天使用官方配置。
- 切换到官方来源但全局 Key 缺失时，聊天返回 `official_api_required`。
- usage event 正确记录 user、provider、model、feature、api_source。

前端：

- 未配置账号时聊天区显示添加入口。
- 添加密钥后模型选择显示对应 provider。
- 模型选择弹窗顶部显示官方 / 个人切换。
- 当前来源有模型可用时不显示未配置提示。
- AI 服务密钥配置弹窗桌面和移动端都不被裁切。
- 删除默认密钥后重新提示配置。
- 普通用户不显示全局配置入口。

## 迁移顺序

1. 建表与加密保存用户 AI 服务密钥。
2. 做用户菜单中的 `AI 服务密钥` 管理界面。
3. 接入 `ApiCredentialResolver` 到聊天链路。
4. 接入联网搜索用户 Tavily Key。
5. 写入 `usage_events`。
6. 将全局配置 UI 文案降级为管理员兼容配置。
7. 增加 `official/personal` 来源切换，并将官方来源预留为未来付费通道。

## 非目标

- 现阶段不做平台代付费。
- 现阶段不做套餐、余额、发票、支付。
- 现阶段不做团队共享 AI 服务密钥。
- 现阶段不做真正的平台 API 池和扣费，只保留官方来源入口与全局配置占位。
