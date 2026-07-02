"""
Bilibili RAG 知识库系统

RAG 服务模块 - 向量存储与问答
"""

import warnings
from typing import List, Optional
from loguru import logger
from langchain.schema import Document
from app.schemas.content import VideoContent
from app.services.rag_collection_ops import (
    clear_collection as clear_collection_vectors,
    collection_stats,
    delete_knowledge_base_vectors,
    delete_video_vectors,
    delete_video_vectors_in_knowledge_base,
    has_video_vectors_in_knowledge_base as has_scoped_video_vectors,
)
from app.services.rag_filters import (
    knowledge_base_filter,
)
from app.services.rag_indexing import index_video_content, index_videos_batch
from app.services.rag_runtime_components import (
    build_embeddings,
    build_fallback_prompt,
    build_llm,
    build_qa_prompt,
    build_summary_prompt,
    build_text_splitter,
    build_vectorstore,
)
from app.services.rag_qa import (
    answer_rag_question,
    complete_rag_answer,
    fallback_rag_answer,
)
from app.services.rag_summary import summarize_text_content


class RAGService:
    """
    RAG 服务

    负责：
    1. 向量存储管理
    2. 文档添加与检索
    3. 问答功能
    """

    def __init__(self, collection_name: str = "bilibili_videos"):
        """
        初始化 RAG 服务

        Args:
            collection_name: 向量集合名称
        """
        self.collection_name = collection_name

        self.embeddings = build_embeddings()
        self.vectorstore = build_vectorstore(collection_name, self.embeddings)
        self.llm = build_llm()
        self.text_splitter = build_text_splitter()
        self.qa_prompt = build_qa_prompt()
        self.fallback_prompt = build_fallback_prompt()
        self.summary_prompt = build_summary_prompt()

    def add_video_content(
        self,
        video: VideoContent,
        workspace_id: int | None = None,
        knowledge_base_id: int | None = None,
        source_binding_id: int | None = None,
    ) -> int:
        """
        添加单个视频内容到向量库

        Args:
            video: VideoContent 对象

        Returns:
            添加的文档块数量
        """
        return index_video_content(
            video,
            text_splitter=self.text_splitter,
            vectorstore=self.vectorstore,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_binding_id=source_binding_id,
            warning_logger=logger.warning,
            info_logger=logger.info,
            error_logger=logger.error,
        )

    def add_videos_batch(
        self, videos: List[VideoContent], progress_callback=None
    ) -> dict:
        """
        批量添加视频到向量库

        Args:
            videos: VideoContent 列表
            progress_callback: 进度回调 callback(current, total, title)

        Returns:
            {"success": 成功数, "failed": 失败数, "chunks": 总块数}
        """
        return index_videos_batch(
            videos,
            add_video_content=self.add_video_content,
            progress_callback=progress_callback,
            error_logger=logger.error,
        )

    def search(
        self, query: str, k: int = 5, bvids: Optional[List[str]] = None
    ) -> List[Document]:
        """
        检索相关内容（已废弃：无多用户范围，请使用 search_in_knowledge_base）
        """
        warnings.warn(
            "RAGService.search() 已废弃，请使用 search_in_knowledge_base() "
            "以确保多用户数据隔离",
            DeprecationWarning,
            stacklevel=2,
        )
        if not query or not query.strip():
            logger.warning("检索查询为空")
            return []

        try:
            if bvids:
                docs = self.vectorstore.similarity_search(
                    query, k=k, filter={"bvid": {"$in": bvids}}
                )
            else:
                docs = self.vectorstore.similarity_search(query, k=k)

            logger.info(f"检索完成：query='{query}'，召回={len(docs)}")
            for idx, doc in enumerate(docs):
                meta = doc.metadata or {}
                title = meta.get("title", "")
                bvid = meta.get("bvid", "")
                chunk_index = meta.get("chunk_index", "")
                preview = doc.page_content[:120].replace("\n", " ").strip()
                logger.info(f"召回[{idx+1}] {bvid} #{chunk_index} {title} | {preview}")

            return docs
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            return []

    def search_in_knowledge_base(
        self,
        query: str,
        workspace_id: int,
        knowledge_base_id: int,
        k: int = 5,
        bvids: Optional[List[str]] = None,
    ) -> List[Document]:
        if not query or not query.strip():
            return []

        return self.vectorstore.similarity_search(
            query,
            k=k,
            filter=knowledge_base_filter(
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                bvids=bvids,
            ),
        )

    async def _fallback_answer(self, question: str, reason: str = "") -> dict:
        """
        当没有检索到内容时，让 AI 自然回复

        Args:
            question: 用户问题
            reason: 原因说明

        Returns:
            回答结果
        """
        return await fallback_rag_answer(
            question,
            reason,
            fallback_prompt=self.fallback_prompt,
            llm=self.llm,
        )

    async def answer_question(
        self, question: str, k: int = 5, bvids: Optional[List[str]] = None
    ) -> dict:
        """
        回答问题

        Args:
            question: 用户问题
            k: 检索文档数量
            bvids: 可选，限制在这些视频范围内搜索

        Returns:
            {
                "answer": 回答内容,
                "sources": 来源视频列表
            }
        """
        return await answer_rag_question(
            question,
            k=k,
            bvids=bvids,
            get_collection_stats=self.get_collection_stats,
            search_documents=self.search,
            fallback_answer=self._fallback_answer,
            complete_answer=self._complete_answer,
        )

    async def _complete_answer(self, question: str, context: str) -> str:
        return await complete_rag_answer(
            question,
            context,
            qa_prompt=self.qa_prompt,
            llm=self.llm,
        )

    async def summarize_content(self, content: str) -> str:
        """
        使用 LLM 总结内容（用于字幕内容）

        Args:
            content: 原始内容（字幕文本）

        Returns:
            总结后的内容
        """
        return await summarize_text_content(
            content,
            summary_prompt=self.summary_prompt,
            llm=self.llm,
        )

    def get_collection_stats(self) -> dict:
        """
        获取向量库统计信息

        Returns:
            统计信息字典
        """
        return collection_stats(
            self.vectorstore._collection,
            collection_name=self.collection_name,
        )

    def clear_collection(self):
        """清空向量库"""
        try:
            clear_collection_vectors(self.vectorstore._collection)
            logger.info(f"已清空向量库: {self.collection_name}")
        except Exception as e:
            logger.error(f"清空向量库失败: {e}")
            raise

    def delete_video(self, bvid: str):
        """
        删除指定视频的所有文档块

        Args:
            bvid: 视频 BV 号
        """
        try:
            delete_video_vectors(self.vectorstore._collection, bvid=bvid)
            logger.info(f"已删除视频: {bvid}")
        except Exception as e:
            logger.error(f"删除视频失败 [{bvid}]: {e}")
            raise

    def delete_video_in_knowledge_base(
        self,
        workspace_id: int,
        knowledge_base_id: int,
        bvid: str,
    ):
        """Delete one video's vectors inside a single knowledge-base scope."""
        try:
            delete_video_vectors_in_knowledge_base(
                self.vectorstore._collection,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                bvid=bvid,
            )
            logger.info(f"已删除知识库 {knowledge_base_id} 内的视频 {bvid}")
        except Exception as e:
            logger.error(f"删除 scoped 视频失败 [{knowledge_base_id}/{bvid}]: {e}")
            raise

    def has_video_vectors_in_knowledge_base(
        self,
        *,
        workspace_id: int,
        knowledge_base_id: int,
        bvid: str,
    ) -> bool:
        """Return whether one video already has vectors in the scoped collection."""
        try:
            return has_scoped_video_vectors(
                self.vectorstore._collection,
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                bvid=bvid,
            )
        except Exception as e:
            logger.warning(
                f"检查 scoped 视频向量失败 [{knowledge_base_id}/{bvid}]: {e}"
            )
            return False

    def delete_by_knowledge_base(
        self,
        knowledge_base_id: int,
        workspace_id: int | None = None,
    ) -> int:
        """
        删除指定知识库的所有向量文档。返回删除前匹配的文档数。

        Args:
            knowledge_base_id: 知识库 ID
        """
        try:
            deleted = delete_knowledge_base_vectors(
                self.vectorstore._collection,
                knowledge_base_id=knowledge_base_id,
                workspace_id=workspace_id,
            )
            logger.info(f"已删除知识库 {knowledge_base_id} 的 {deleted} 个向量文档")
            return deleted
        except Exception as e:
            logger.error(f"删除知识库向量失败 [{knowledge_base_id}]: {e}")
            raise
