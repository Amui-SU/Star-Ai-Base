"""RAG runtime component builders."""

from langchain.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from loguru import logger

from app.config import settings


def build_embeddings():
    try:
        from langchain_community.embeddings import DashScopeEmbeddings

        embeddings = DashScopeEmbeddings(
            dashscope_api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )
        logger.info("使用 DashScopeEmbeddings 初始化成功")
        return embeddings
    except ImportError:
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.embedding_model,
            check_embedding_ctx_length=False,
        )


def build_vectorstore(collection_name: str, embeddings):
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_directory,
    )


def build_llm():
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        temperature=0.5,
    )


def build_text_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )


def build_qa_prompt():
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个知识库助手，专门基于用户收藏的 B站视频内容来回答问题。

请遵循以下规则：
1. 根据提供的视频内容来回答问题
2. 回答要自然、友好、有条理
3. 可以引用相关的视频标题作为来源
4. 如果多个视频涉及相同话题，请综合它们的内容

视频内容：
{context}
""",
            ),
            ("human", "{question}"),
        ]
    )


def build_fallback_prompt():
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个友好的助手。用户在使用一个B站收藏夹知识库系统。

当前情况：知识库中没有找到与用户问题相关的内容。

请：
1. 友好地回应用户的问题
2. 如果能根据常识简单回答，可以简要回答
3. 建议用户构建更多收藏夹内容，或者换个问法
4. 保持自然、不要死板
""",
            ),
            ("human", "{question}"),
        ]
    )


def build_summary_prompt():
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个内容总结专家。请对以下视频字幕内容进行总结。

要求：
1. 提取核心要点（3-5个）
2. 生成一段简洁的总结（100-200字）
3. 保持原意，不要添加额外信息

字幕内容：""",
            ),
            ("human", "{content}"),
        ]
    )
