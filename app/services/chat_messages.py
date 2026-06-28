"""Pure chat message and prompt assembly helpers."""


def build_overview_messages(context: str, question: str) -> list[dict]:
    system = (
        "你是一个收藏夹知识库助手。用户想要了解他们收藏夹的整体内容。\n"
        "请根据以下视频信息回答用户的问题。回答要：\n"
        "1. 自然、友好、有条理\n"
        "2. 可以总结、分类、提炼要点\n"
        "3. 如果内容较多，挑选代表性的进行介绍\n\n"
        f"收藏夹内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def build_rag_messages(context: str, question: str) -> list[dict]:
    system = (
        "你是一个知识库助手，基于用户收藏的视频内容回答问题。\n"
        "请根据以下检索到的视频内容回答：\n"
        "1. 直接回答问题，引用相关内容\n"
        "2. 回答要自然、有条理\n"
        "3. 可以引用视频标题作为来源\n\n"
        f"相关内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def build_fallback_messages(context: str, question: str) -> list[dict]:
    system = (
        "你是一个收藏夹知识库助手。\n"
        "用户的问题在现有知识库中没有检索到直接内容。\n"
        "以下是用户收藏夹中的视频概览（如果为空说明用户还没入库）：\n"
        f"{context}\n\n"
        "请根据以上信息（如果有）：\n"
        "1. 尝试回答用户问题\n"
        "2. 如果没有任何视频信息，礼貌地告诉用户需要先在左侧选择收藏夹并点击「入库」或者「更新」\n"
        '3. 保持像真人助手一样的语气，不要显示这是"备选方案"'
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def build_direct_messages(question: str) -> list[dict]:
    """通用回答（不查库）"""
    system = (
        "你是一个知识库问答助手。\n" "请直接回答用户问题，避免引入收藏夹或知识库内容。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def build_direct_messages_with_context(context: str, question: str) -> list[dict]:
    """带收藏夹上下文的通用回答（引导用户提问）"""
    system = (
        "你是一个知识库问答助手。\n"
        "以下是用户收藏夹的概览（收藏夹名称与视频标题）：\n"
        f"{context}\n\n"
        "请先回答用户问题，再根据收藏夹内容引导用户提出与收藏相关的问题。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def enforce_markdown_output(messages: list[dict]) -> list[dict]:
    """统一要求模型输出 Markdown，便于前端结构化渲染。"""
    if not messages:
        return messages

    markdown_instruction = (
        "输出要求：必须使用 Markdown 格式回答，并严格遵守以下规则：\n"
        "1) 先给一个二级标题（例如：## 回答要点）；\n"
        "2) 要点必须使用短横线或数字列表；\n"
        "3) 关键信息必须用 **加粗**；\n"
        "4) 补充说明必须至少包含一个 > 引用块；\n"
        "5) 代码必须使用带语言标识的三反引号代码块；\n"
        "6) 需要对比时使用 Markdown 表格；\n"
        "7) 禁止输出 HTML 标签。\n\n"
        "示例结构（仅示例，内容按用户问题生成）：\n"
        "## 回答要点\n"
        "- **重点1**：xxx\n"
        "- **重点2**：xxx\n\n"
        "> 补充说明：xxx"
    )

    normalized_messages = [dict(message) for message in messages]
    first = normalized_messages[0]
    if first.get("role") == "system":
        content = str(first.get("content") or "")
        if "Markdown" not in content and "markdown" not in content:
            first["content"] = f"{content}\n\n{markdown_instruction}"
    else:
        normalized_messages.insert(
            0, {"role": "system", "content": markdown_instruction}
        )
    return normalized_messages


def apply_mode_instructions(messages: list[dict], thinking_enabled: bool) -> list[dict]:
    """根据当前模型配置补充思考模式指令。"""
    if not thinking_enabled:
        return messages

    mode_instruction = (
        "已开启深度思考模式。请使用模型原生 reasoning/thinking 通道进行推理，"
        "最终回答保持清晰简洁；不要在正文中伪造或重复思考过程。"
    )
    normalized = [dict(message) for message in messages]
    first = normalized[0] if normalized else None
    if first and first.get("role") == "system":
        first["content"] = f"{first.get('content')}\n\n{mode_instruction}"
    else:
        normalized.insert(0, {"role": "system", "content": mode_instruction})
    return normalized


def build_db_list_messages(context: str, question: str) -> list[dict]:
    """仅用标题/简介回答列表类问题"""
    system = (
        "你是一个收藏夹知识库助手。\n"
        "用户需要清单/列表类答案，请基于以下视频标题与简介回答。\n"
        "回答要：\n"
        "1. 按收藏夹或主题分组\n"
        "2. 只输出与问题相关的条目\n"
        "3. 简洁清晰\n\n"
        f"收藏夹内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def build_db_summary_messages(context: str, question: str) -> list[dict]:
    """仅用数据库内容回答总结类问题"""
    system = (
        "你是一个收藏夹知识库助手。\n"
        "用户需要总结/提炼，请基于以下视频内容回答。\n"
        "回答要：\n"
        "1. 提炼重点与要点\n"
        "2. 结构清晰、可快速理解\n"
        "3. 必要时引用视频标题作为来源\n\n"
        f"收藏夹内容：\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
