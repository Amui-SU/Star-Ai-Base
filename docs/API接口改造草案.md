# API 接口改造草案

## 目标

用系统登录态和知识库范围替代旧的 `session_id` query 参数，避免不同用户的数据混在同一套收藏、向量和问答接口中。

## 系统账号接口

- `POST /system-auth/register`
- `POST /system-auth/login`
- `POST /system-auth/logout`
- `GET /system-auth/me`

系统身份只从 HttpOnly Cookie 读取，前端不直接持有系统 session token。

## 内容源绑定接口

- `GET /source-bindings`
- `DELETE /source-bindings/{binding_id}`
- `GET /source-bindings/bilibili/qrcode`
- `GET /source-bindings/bilibili/qrcode/poll/{qrcode_key}`

B 站扫码只用于绑定外部内容源。绑定结果写入当前系统用户和当前工作区。

## 知识库接口

已实现的多用户范围化入口：

- `GET /knowledge-bases`
- `POST /knowledge-bases`
- `GET /knowledge-bases/{knowledge_base_id}/stats`
- `POST /knowledge-bases/{knowledge_base_id}/search`
- `POST /knowledge-bases/{knowledge_base_id}/chat`
- `POST /knowledge-bases/{knowledge_base_id}/chat/stream`
- `POST /knowledge-bases/{knowledge_base_id}/build`

所有知识库 ID 必须属于当前用户可访问的工作区。新入口不接受 `session_id` 作为身份来源。

## 旧接口处理

第一阶段保留旧接口用于本地兼容，但前端新功能不再调用：

- `GET /auth/qrcode`
- `GET /auth/qrcode/poll/{qrcode_key}`
- `GET /favorites/list?session_id=...`
- `POST /knowledge/build?session_id=...`
- `POST /chat/ask`
- `POST /chat/search`

后续阶段应给旧接口增加明确的兼容模式开关，尤其要限制全局删除、清空和无范围检索接口。

## 安全规则

- 系统身份只从 HttpOnly Cookie 读取。
- 内容源绑定 ID 必须属于当前用户和当前工作区。
- 知识库 ID 必须属于当前工作区。
- 检索接口必须带 `workspace_id` 和 `knowledge_base_id` 过滤。
- 新写入向量必须携带 `workspace_id`、`knowledge_base_id`、`source_binding_id` 元数据。
- 不提供跨用户、跨工作区的全局删除或清空接口。

## 前端调用建议

- 页面初始化先调用 `GET /system-auth/me` 判断登录态。
- 未登录用户进入系统注册/登录流程。
- 登录后先拉取 `GET /knowledge-bases` 和 `GET /source-bindings`。
- 构建知识库前要求用户选择目标知识库和内容源绑定。
- 聊天、搜索、统计都从 `/knowledge-bases/{knowledge_base_id}/...` 进入。
