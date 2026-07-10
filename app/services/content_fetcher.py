"""
Bilibili RAG 知识库系统

视频内容获取服务 - 二级降级策略
"""

from typing import Optional
import asyncio
from loguru import logger
from app.schemas.content import ContentSource, VideoContent
from app.services.bilibili import BilibiliService
from app.services.asr import ASRService
from app.services.content_audio_runtime import (
    get_audio_duration_sec,
    split_audio_wav,
    transcode_audio_to_wav,
)
from app.services.content_summary import (
    format_ai_summary_content,
    parse_ai_summary_result,
)
from app.services.content_subtitles import (
    try_bilibili_subtitle,
    try_bilibili_subtitle_with_timeline,
)
from app.services.content_asr import try_bilibili_asr


class ContentFetcher:
    """
    视频内容获取器

    采用二级降级策略：
    1. 音频转写（ASR）
    2. 视频基本信息 (兜底)
    """

    def __init__(self, bilibili_service: BilibiliService, asr_service: ASRService):
        self.bili = bilibili_service
        self.asr = asr_service

    async def fetch_content(
        self, bvid: str, cid: int = None, title: str = None
    ) -> VideoContent:
        """
        获取视频内容，自动降级

        Args:
            bvid: 视频 BV 号
            cid: 视频 cid (如果没有会自动获取)
            title: 视频标题 (如果没有会自动获取)

        Returns:
            VideoContent 对象
        """
        # 获取视频基本信息。即使收藏夹列表已给出 cid/title，也需要详情里的
        # aid、owner、desc 和字幕列表，后续摘要/字幕/简介都依赖这些字段。
        video_info = None
        try:
            video_info = await self.bili.get_video_info(bvid)
            if not cid:
                cid = video_info.get("cid")
            if not title:
                title = video_info.get("title", "未知标题")
        except Exception as e:
            if not cid or not title:
                logger.error(f"获取视频信息失败 [{bvid}]: {e}")
                return VideoContent(
                    bvid=bvid,
                    title=title or "未知标题",
                    content="无法获取视频信息",
                    source=ContentSource.BASIC_INFO,
                )
            logger.debug(f"[{bvid}] 获取视频信息失败，继续使用收藏夹元数据: {e}")

        description = video_info.get("desc", "") if video_info else ""

        summary: Optional[dict] = None

        # Level 1: 字幕正文。完整正文比平台摘要更适合知识库检索和后续笔记 AI 分析。
        subtitle_timeline = None
        if cid:
            subtitle_result = await self._try_subtitle_with_timeline(
                bvid, cid, video_info=video_info
            )
            if subtitle_result:
                subtitle_text, subtitle_timeline = subtitle_result
                logger.info(f"[{bvid}] 使用字幕文本（含时间轴）")
                summary = await self._try_ai_summary_for_outline(bvid, cid, video_info)
                return VideoContent(
                    bvid=bvid,
                    title=title,
                    content=subtitle_text,
                    source=ContentSource.SUBTITLE,
                    outline=summary.get("outline") if summary else None,
                    subtitle_timeline=subtitle_timeline,
                )

        # Level 2: 音频 ASR
        logger.info(f"[{bvid}] 尝试使用 ASR")

        asr_text = await self._try_asr(bvid, cid)
        if asr_text:
            logger.info(f"[{bvid}] 使用 ASR 文本")
            summary = await self._try_ai_summary_for_outline(bvid, cid, video_info)
            return VideoContent(
                bvid=bvid,
                title=title,
                content=asr_text,
                source=ContentSource.ASR,
                outline=summary.get("outline") if summary else None,
            )

        # Level 3: B 站 AI 摘要。仅在没有完整正文时作为兜底内容。
        if cid:
            summary = summary or await self._try_ai_summary_for_outline(
                bvid, cid, video_info
            )
            if summary:
                logger.info(f"[{bvid}] 使用 AI 摘要")
                return VideoContent(
                    bvid=bvid,
                    title=title,
                    content=format_ai_summary_content(summary),
                    source=ContentSource.AI_SUMMARY,
                    outline=summary.get("outline"),
                )

        # ASR 失败时，补齐基础信息（避免遗漏简介）
        if not video_info:
            try:
                video_info = await self.bili.get_video_info(bvid)
            except Exception as e:
                logger.debug(f"[{bvid}] 获取视频信息失败(兜底): {e}")

        if video_info and not description:
            description = video_info.get("desc", "") or description

        # Level 4: 使用基本信息兜底
        logger.info(f"[{bvid}] 使用基本信息")
        basic_content = f"视频标题：{title}"
        if description:
            basic_content += f"\n\n视频简介：{description}"

        return VideoContent(
            bvid=bvid,
            title=title,
            content=basic_content,
            source=ContentSource.BASIC_INFO,
        )

    async def _try_asr(self, bvid: str, cid: int) -> Optional[str]:
        """尝试进行音频转写"""
        return await try_bilibili_asr(self.bili, self.asr, bvid, cid)

    def _transcode_audio_to_wav(self, bvid: str, file_path: str) -> Optional[str]:
        """使用 ffmpeg 转码为 16k 单声道 wav，提高 ASR 兼容性"""
        return transcode_audio_to_wav(bvid, file_path)

    def _get_audio_duration_sec(self, file_path: str) -> Optional[float]:
        return get_audio_duration_sec(file_path)

    def _split_audio_wav(
        self, bvid: str, wav_path: str, segment_seconds: int = 1200
    ) -> list[str]:
        """将较长 wav 切分为多段，提升 ASR 成功率"""
        return split_audio_wav(bvid, wav_path, segment_seconds)

    async def _try_ai_summary(
        self, bvid: str, cid: int, up_mid: int = None
    ) -> Optional[dict]:
        """尝试获取 AI 摘要"""
        try:
            result = await self.bili.get_video_summary(bvid, cid, up_mid)

            if not result:
                return None

            summary = parse_ai_summary_result(result)
            if summary is None and result.get("code", -1) != 0:
                logger.debug(f"[{bvid}] AI 摘要不可用: code={result.get('code', -1)}")
                return None
            if summary is None:
                logger.debug(f"[{bvid}] AI 摘要为空")
                return None
            return summary

        except Exception as e:
            logger.warning(f"[{bvid}] 获取 AI 摘要失败: {e}")
            return None

    async def _try_ai_summary_for_outline(
        self, bvid: str, cid: int, video_info: Optional[dict]
    ) -> Optional[dict]:
        owner = (video_info or {}).get("owner") or {}
        up_mid = owner.get("mid") or (video_info or {}).get("owner_mid")
        return await self._try_ai_summary(bvid, cid, up_mid=up_mid)

    async def _try_subtitle(
        self, bvid: str, cid: int, video_info: Optional[dict] = None
    ) -> Optional[str]:
        """尝试获取字幕"""
        return await try_bilibili_subtitle(
            self.bili,
            bvid,
            cid,
            video_info=video_info,
        )

    async def _try_subtitle_with_timeline(
        self, bvid: str, cid: int, video_info: Optional[dict] = None
    ) -> Optional[tuple[str, list[dict]]]:
        """尝试获取字幕和完整时间轴"""
        return await try_bilibili_subtitle_with_timeline(
            self.bili,
            bvid,
            cid,
            video_info=video_info,
        )

    async def fetch_all_videos_content(
        self, videos: list, progress_callback=None
    ) -> list[VideoContent]:
        """
        批量获取视频内容

        Args:
            videos: 视频列表，每个元素需包含 bvid, title (可选 cid)
            progress_callback: 进度回调函数 callback(current, total, video_title)

        Returns:
            VideoContent 列表
        """
        import asyncio

        results = []
        total = len(videos)

        for i, video in enumerate(videos):
            bvid = video.get("bvid") or video.get("bv_id")
            title = video.get("title", "")
            cid = video.get("cid") or video.get("id")

            if not bvid:
                logger.warning(f"跳过无效视频: {video}")
                continue

            try:
                content = await self.fetch_content(bvid, cid, title)
                results.append(content)

                if progress_callback:
                    progress_callback(i + 1, total, title)

            except Exception as e:
                logger.error(f"处理视频失败 [{bvid}]: {e}")
                results.append(
                    VideoContent(
                        bvid=bvid,
                        title=title or bvid,
                        content=f"处理失败: {str(e)}",
                        source=ContentSource.BASIC_INFO,
                    )
                )

            # 控制请求速率
            await asyncio.sleep(0.5)

        return results
