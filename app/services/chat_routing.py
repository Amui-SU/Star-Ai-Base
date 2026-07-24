"""Pure chat question classification and routing helpers."""

import re
from collections.abc import Callable
from typing import Any, Optional

from langchain.schema import Document

from app.services.api_account_requests import build_account_request_options


def is_list_question(question: str) -> bool:
    """列表/清单类问题"""
    list_terms = [
        "有哪些",
        "有什么",
        "列表",
        "清单",
        "目录",
        "都有哪些",
        "列出",
        "罗列",
        "多少个",
        "几个",
    ]
    return any(term in question for term in list_terms)


def is_summary_question(question: str) -> bool:
    """总结/概括类问题"""
    summary_terms = [
        "总结",
        "概述",
        "概括",
        "分析",
        "梳理",
        "提炼",
        "回顾",
        "复盘",
        "要点",
        "重点",
        "关键点",
        "核心",
        "讲了什么",
        "讲些什么",
    ]
    return any(term in question for term in summary_terms)


def is_general_question(question: str) -> bool:
    """通用闲聊/与收藏无关的问题"""
    general_terms = [
        "你好",
        "嗨",
        "哈喽",
        "hello",
        "hi",
        "在吗",
        "你是谁",
        "你能做什么",
        "谢谢",
        "晚安",
        "早安",
        "早上好",
    ]
    cleaned = re.sub(r"[\\W_]+", "", question, flags=re.UNICODE)
    lowered = cleaned.lower()
    residual = lowered
    for term in general_terms:
        residual = residual.replace(term.lower(), "")
    return residual == ""


def is_collection_intent(question: str) -> bool:
    """是否显式指向收藏/视频/知识库"""
    terms = [
        "收藏",
        "收藏夹",
        "视频",
        "合集",
        "up主",
        "BV",
        "bv",
        "分P",
        "字幕",
        "知识库",
        "入库",
        "同步",
        "向量",
        "检索",
    ]
    return any(term in question for term in terms)


def is_overview_question(question: str) -> bool:
    """概览类问题（列表或总结）"""
    return is_list_question(question) or is_summary_question(question)


def route_with_rules(question: str, is_collection_intent: bool, related: bool) -> str:
    """规则路由兜底"""
    if is_general_question(question) and not is_collection_intent:
        return "direct"
    if is_list_question(question):
        return "db_list"
    if is_summary_question(question):
        return "db_content"
    if not related and not is_collection_intent:
        return "direct"
    return "vector"


def route_with_llm(
    question: str,
    *,
    resolve_llm_config: Callable[[], dict[str, Any]],
    get_llm_client: Callable[[dict[str, Any]], Any],
    log_warning: Optional[Callable[[str], None]] = None,
) -> tuple[Optional[str], str]:
    """使用 LLM 进行路由判断"""
    try:
        llm_config = resolve_llm_config()
        client = get_llm_client(llm_config)
        system = (
            "你是一个路由器，只输出以下之一：direct, db_list, db_content, vector。\n"
            "规则：\n"
            "- direct：寒暄/闲聊/与收藏无关的问题\n"
            "- db_list：清单/列表/目录/有哪些\n"
            "- db_content：明确要求“全部/所有/整体/概览/全库”内容的总结\n"
            "- vector：具体主题问题或需要“先检索再总结”的问题\n"
            "示例：\n"
            "Q: 中西方文化的差异是什么，简单总结 -> vector\n"
            "Q: 概览我收藏夹里所有王德峰相关内容 -> db_content\n"
            "只输出一个词，不要解释。"
        )
        resp = client.chat.completions.create(
            model=llm_config["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            **build_account_request_options(llm_config, system_body={"temperature": 0}),
        )
        text = (resp.choices[0].message.content or "").strip()
        match = re.search(r"(direct|db_list|db_content|vector)", text)
        return (match.group(1) if match else None), text
    except Exception as e:
        if log_warning is not None:
            log_warning(f"LLM 路由失败 ({type(e).__name__})")
        return None, ""


def extract_keywords(question: str) -> list[str]:
    """提取用于过滤的关键词"""
    stopwords = {
        "什么",
        "怎么",
        "如何",
        "是否",
        "可以",
        "哪个",
        "哪些",
        "请问",
        "一下",
        "为什么",
        "有没有",
        "能不能",
        "能否",
        "是不是",
        "是什么",
        "多少",
        "哪里",
        "讲讲",
        "介绍",
        "总结",
        "概括",
        "分析",
        "解释",
        "说明",
        "评价",
        "区别",
        "内容",
        "视频",
    }
    keywords: list[str] = []
    for kw in re.findall(r"[\u4e00-\u9fff]{2,}", question):
        if kw not in stopwords and kw not in keywords:
            keywords.append(kw)
    for kw in re.findall(r"[A-Za-z0-9]{2,}", question):
        if kw not in keywords:
            keywords.append(kw)
    return keywords


def filter_docs_by_keywords(docs: list[Document], question: str) -> list[Document]:
    """根据关键词过滤召回内容，减少噪声"""
    keywords = extract_keywords(question)
    if not keywords:
        return []
    filtered: list[Document] = []
    for doc in docs:
        meta = doc.metadata or {}
        title = meta.get("title", "") or ""
        content = doc.page_content or ""
        if any(kw in title for kw in keywords) or any(kw in content for kw in keywords):
            filtered.append(doc)
    return filtered
