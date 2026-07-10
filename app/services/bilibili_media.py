"""Media parsing and download helpers for Bilibili API responses."""

from typing import Any, Mapping, Optional

from loguru import logger


ASR_AUDIO_BANDWIDTH_LIMIT = 64_000


def normalize_bilibili_media_url(url: str) -> str:
    """Normalize protocol-relative Bilibili media URLs."""
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _audio_bandwidth(item: Mapping[str, Any]) -> int:
    value = item.get("bandwidth") or item.get("bandWidth") or 0
    try:
        return int(value)
    except Exception:
        return 0


def _audio_url(item: Mapping[str, Any]) -> Optional[str]:
    return item.get("baseUrl") or item.get("base_url") or item.get("url")


def select_audio_url_from_playurl_payload(payload: Mapping[str, Any]) -> Optional[str]:
    """Select an audio URL from Bilibili playurl response data."""
    dash = (payload or {}).get("dash") or {}
    audio_list = dash.get("audio") or []
    if audio_list:
        candidates = [item for item in audio_list if _audio_bandwidth(item) > 0]
        if candidates:
            preferred = [
                item
                for item in candidates
                if _audio_bandwidth(item) <= ASR_AUDIO_BANDWIDTH_LIMIT
            ]
            if preferred:
                best = max(preferred, key=_audio_bandwidth)
            else:
                best = min(candidates, key=_audio_bandwidth)
        else:
            best = audio_list[0]
        return _audio_url(best)

    durl = (payload or {}).get("durl") or []
    if durl:
        return durl[0].get("url")

    return None


def subtitle_text_from_payload(data: Mapping[str, Any]) -> str:
    """Join Bilibili subtitle body entries into plain text."""
    texts = []
    for item in (data or {}).get("body", []):
        content = item.get("content", "")
        if content:
            texts.append(content)
    return "\n".join(texts)


def subtitle_with_timeline_from_payload(
    data: Mapping[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    """
    提取字幕文本和完整时间轴数据

    Args:
        data: B站字幕API响应数据

    Returns:
        (text, timeline)
        - text: 纯文本内容（用于向量检索）
        - timeline: 完整时间轴数据（用于AI时间戳精确定位）
          格式: [{"from": 0.0, "to": 3.5, "content": "文本"}, ...]
    """
    texts = []
    timeline = []

    for item in (data or {}).get("body", []):
        content = item.get("content", "")
        if content:
            texts.append(content)
            timeline.append(
                {
                    "from": item.get("from", 0),
                    "to": item.get("to", 0),
                    "content": content,
                }
            )

    return "\n".join(texts), timeline


async def download_bilibili_audio_to_file(
    client: Any,
    audio_url: str,
    file_path: str,
    *,
    headers: Mapping[str, str],
    cookies: Mapping[str, str],
) -> bool:
    """Download a Bilibili audio stream to a local file."""
    if not audio_url:
        return False

    try:
        async with client.stream(
            "GET",
            audio_url,
            headers=dict(headers),
            cookies=dict(cookies),
        ) as resp:
            if resp.status_code not in (200, 206):
                logger.warning(
                    f"下载音频失败: status_code={resp.status_code} url={audio_url}"
                )
                return False
            with open(file_path, "wb") as file_obj:
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    file_obj.write(chunk)
        return True
    except Exception as exc:
        logger.warning(f"下载音频异常: {exc}")
        return False
