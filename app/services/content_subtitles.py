"""Subtitle selection and fetch helpers for Bilibili content ingestion."""

from typing import Any, Optional

from loguru import logger


def _is_chinese_subtitle(subtitle: dict[str, Any]) -> bool:
    language = subtitle.get("lan", "") or ""
    return "zh" in language.lower() or "cn" in language.lower()


def pick_preferred_subtitle(subtitles: list[dict[str, Any]]) -> Optional[dict]:
    """Prefer manual Chinese subtitles, then any Chinese subtitle, then first item."""
    if not subtitles:
        return None

    for subtitle in subtitles:
        if (
            _is_chinese_subtitle(subtitle)
            and str(subtitle.get("ai_status", "0")) == "0"
        ):
            return subtitle
    for subtitle in subtitles:
        if _is_chinese_subtitle(subtitle):
            return subtitle
    return subtitles[0]


def extract_subtitles(data: dict[str, Any]) -> list[dict[str, Any]]:
    subtitle_block = (data or {}).get("subtitle", {}) or {}
    return subtitle_block.get("subtitles") or subtitle_block.get("list") or []


def extract_subtitle_url(subtitle: dict[str, Any]) -> str:
    return subtitle.get("subtitle_url") or subtitle.get("url") or ""


async def _download_selected_subtitle(
    bili: Any,
    bvid: str,
    subtitles: list[dict[str, Any]],
    *,
    success_suffix: str = "",
) -> Optional[str]:
    selected_subtitle = pick_preferred_subtitle(subtitles)
    subtitle_url = extract_subtitle_url(selected_subtitle or {})
    if subtitle_url:
        subtitle_text = await bili.download_subtitle(subtitle_url)
        if subtitle_text and len(subtitle_text) >= 50:
            preview = subtitle_text[:120].replace("\n", " ").strip()
            logger.info(
                f"[{bvid}] 字幕获取成功{success_suffix}，长度={len(subtitle_text)}，预览：{preview}"
            )
            return subtitle_text
        logger.info(f"[{bvid}] 字幕内容过少，已忽略")
    else:
        logger.info(f"[{bvid}] 字幕地址为空，无法下载")
    return None


async def try_bilibili_subtitle(
    bili: Any,
    bvid: str,
    cid: int,
    *,
    video_info: Optional[dict] = None,
) -> Optional[str]:
    """Fetch Bilibili subtitle text using player info and view fallbacks."""
    try:
        cookies = bili._get_cookies()
        has_login = bool(cookies.get("SESSDATA"))

        aid = video_info.get("aid") if video_info else None
        player_info = await bili.get_player_info(bvid, cid, aid=aid)

        subtitles = extract_subtitles(player_info or {})
        if subtitles:
            subtitle_text = await _download_selected_subtitle(bili, bvid, subtitles)
            if subtitle_text:
                return subtitle_text
        else:
            logger.info(
                f"[{bvid}] 播放器字幕为空（登录态={'已设置' if has_login else '未设置'}）"
            )

        if not video_info:
            try:
                video_info = await bili.get_video_info(bvid)
            except Exception as exc:
                logger.debug(f"[{bvid}] 获取视频信息失败(字幕兜底): {exc}")
                video_info = None

        if video_info and not aid:
            aid = video_info.get("aid")
            if aid:
                player_info = await bili.get_player_info(bvid, cid, aid=aid)
                subtitles = extract_subtitles(player_info or {})
                if subtitles:
                    subtitle_text = await _download_selected_subtitle(
                        bili,
                        bvid,
                        subtitles,
                        success_suffix="(补aid)",
                    )
                    if subtitle_text:
                        return subtitle_text
                else:
                    logger.info(f"[{bvid}] 播放器字幕仍为空（aid 已补齐）")

        view_subtitles = (video_info or {}).get("subtitle", {}).get("list") or []
        if view_subtitles:
            subtitle_text = await _download_selected_subtitle(
                bili,
                bvid,
                view_subtitles,
                success_suffix="(view兜底)",
            )
            if subtitle_text:
                return subtitle_text
        else:
            logger.info(f"[{bvid}] view 字幕列表为空，无法兜底")

        logger.info(f"[{bvid}] 没有可用字幕，回退到简介兜底")
        return None

    except Exception as exc:
        logger.warning(f"[{bvid}] 获取字幕失败: {exc}")
        return None
