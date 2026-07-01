"""ASR audio helpers for Bilibili content ingestion."""

import os
import time
from collections.abc import Callable
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from loguru import logger


async def probe_audio_url(bvid: str, audio_url: str) -> Optional[int]:
    """Probe whether an audio URL is reachable without Bilibili cookies."""
    try:
        parsed = urlparse(audio_url)
        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        safe_url = "unknown"

    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        status = None
        try:
            head = await client.head(audio_url)
            status = head.status_code
        except Exception as exc:
            logger.info(f"[{bvid}] 音频 URL HEAD 失败: {exc}")

        if status is None or status >= 400:
            try:
                headers = {"Range": "bytes=0-0"}
                get = await client.get(audio_url, headers=headers)
                status = get.status_code
            except Exception as exc:
                logger.info(f"[{bvid}] 音频 URL GET 失败: {exc}")

    if status is None:
        logger.info(f"[{bvid}] 音频 URL 不可达: {safe_url}")
    else:
        logger.info(f"[{bvid}] 音频 URL 可达性: {status} - {safe_url}")
    return status


async def try_asr_with_local_audio(
    bili: Any,
    asr: Any,
    bvid: str,
    cid: int,
    audio_url: str,
    *,
    tmp_dir: str = os.path.join("data", "asr_tmp"),
    time_provider: Callable[[], float] = time.time,
    path_exists: Callable[[str], bool] = os.path.exists,
    get_file_size: Callable[[str], int] = os.path.getsize,
    remove_file: Callable[[str], None] = os.remove,
) -> Optional[str]:
    """Download audio locally and run ASR Recognition directly."""
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        parsed = urlparse(audio_url)
        ext = os.path.splitext(parsed.path)[1] or ".m4s"
    except Exception:
        ext = ".m4s"

    filename = f"{bvid}_{cid}_{int(time_provider())}{ext}"
    file_path = os.path.join(tmp_dir, filename)

    ok = await bili.download_audio_to_file(audio_url, file_path)
    if not ok:
        logger.info(f"[{bvid}] 本地下载音频失败")
        return None

    if path_exists(file_path) and get_file_size(file_path) < 1024:
        logger.info(f"[{bvid}] 本地音频文件过小，跳过上传")
        try:
            remove_file(file_path)
        except Exception:
            logger.debug(f"[{bvid}] 清理过小音频失败: {file_path}")
        return None

    text = await asr.transcribe_local_file(file_path)
    if text:
        preview = text[:120].replace("\n", " ").strip()
        logger.info(f"[{bvid}] Recognition ASR 成功，长度={len(text)}，预览：{preview}")
    return text


async def _resolve_probe_result(
    probe_audio: Callable[[str, str], Any],
    bvid: str,
    audio_url: str,
) -> Optional[int]:
    status = probe_audio(bvid, audio_url)
    if hasattr(status, "__await__"):
        return await status
    return status


async def try_bilibili_asr(
    bili: Any,
    asr: Any,
    bvid: str,
    cid: int,
    *,
    probe_audio: Callable[[str, str], Any] = probe_audio_url,
    local_audio_transcriber: Callable[..., Any] = try_asr_with_local_audio,
    min_text_length: int = 50,
    **local_audio_kwargs,
) -> Optional[str]:
    """Fetch Bilibili audio and return ASR text using remote or local fallback."""
    try:
        audio_url = await bili.get_audio_url(bvid, cid)
        if not audio_url:
            logger.info(f"[{bvid}] 未获取到音频 URL")
            return None

        status = await _resolve_probe_result(probe_audio, bvid, audio_url)
        if status is not None and status < 400:
            logger.info(f"[{bvid}] 音频 URL 可达，使用 Transcription")
            text = await asr.transcribe_url(audio_url)
        else:
            logger.info(f"[{bvid}] 音频 URL 不可达，使用 Recognition 兜底")
            text = await local_audio_transcriber(
                bili,
                asr,
                bvid,
                cid,
                audio_url,
                **local_audio_kwargs,
            )

        if not text or len(text) < min_text_length:
            logger.info(f"[{bvid}] ASR 内容过少")
            return None
        preview = text[:120].replace("\n", " ").strip()
        logger.info(f"[{bvid}] ASR 成功，长度={len(text)}，预览：{preview}")
        return text
    except Exception as exc:
        logger.warning(f"[{bvid}] ASR 失败: {exc}")
        return None
