"""Remote transcription helpers for DashScope ASR."""

import json
import time
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Optional
from urllib import request as urlrequest

import httpx
import dashscope
from dashscope.audio.asr import Transcription
from dashscope.common.utils import default_headers, join_url
from loguru import logger


OpenUrl = Callable[[str], Any]


def output_value(output: Any, key: str, default=None):
    if isinstance(output, dict):
        return output.get(key, default)
    return getattr(output, key, default)


def download_transcription_text(
    url: str,
    *,
    open_url: OpenUrl = urlrequest.urlopen,
) -> Optional[str]:
    """Download and normalize DashScope transcription result JSON."""
    try:
        raw = open_url(url).read().decode("utf-8")
        data = json.loads(raw)
    except Exception as exc:
        logger.warning(f"ASR 结果下载失败: {exc}")
        return None

    texts = []
    transcripts = data.get("transcripts") or []
    for item in transcripts:
        text = item.get("text", "") or ""
        if text:
            texts.append(text)
            continue
        for sentence in item.get("sentences", []) or []:
            sentence_text = sentence.get("text", "") or ""
            if sentence_text:
                texts.append(sentence_text)

    if not texts and isinstance(data.get("text"), str):
        texts.append(data["text"])

    return "\n".join(texts).strip() if texts else None


def build_dashscope_api_url(
    *parts: str,
    base_url: str | None = None,
) -> str:
    """Build a DashScope API URL from the configured base URL."""
    resolved_base_url = base_url or getattr(dashscope, "base_http_api_url", None)
    if not resolved_base_url:
        resolved_base_url = "https://dashscope.aliyuncs.com/api/v1"
    return join_url(resolved_base_url, *parts)


def submit_transcription_task_restful(
    audio_url: str,
    model: str,
    *,
    api_key: str,
    build_api_url: Callable[..., str],
    default_headers_factory: Callable[[str], dict[str, str]] = default_headers,
    post_json: Callable[..., Any] = httpx.post,
) -> Optional[str]:
    """Submit a DashScope RESTful transcription task and return its task id."""
    url = build_api_url("services", "audio", "asr", "transcription")
    headers = {
        **default_headers_factory(api_key),
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    parameters = {}
    if "paraformer" in model:
        parameters["language_hints"] = ["zh", "en"]
    payload: dict[str, Any] = {"model": model, "input": {"file_urls": [audio_url]}}
    if parameters:
        payload["parameters"] = parameters

    try:
        resp = post_json(url, json=payload, headers=headers, timeout=30.0)
    except Exception as exc:
        logger.warning(f"ASR RESTful 提交失败: {exc}")
        return None

    if resp.status_code != HTTPStatus.OK:
        logger.warning(
            f"ASR RESTful 提交失败: status_code={resp.status_code}, body={resp.text[:300]}"
        )
        return None

    data = resp.json()
    task_id = data.get("task_id")
    if not task_id:
        output = data.get("output") if isinstance(data, dict) else None
        if isinstance(output, dict):
            task_id = output.get("task_id")
    return task_id


def fetch_transcription_task_restful(
    task_id: str,
    *,
    api_key: str,
    build_api_url: Callable[..., str],
    default_headers_factory: Callable[[str], dict[str, str]] = default_headers,
    get_json: Callable[..., Any] = httpx.get,
) -> Optional[dict]:
    """Fetch the current state of a DashScope RESTful transcription task."""
    url = build_api_url("tasks", task_id)
    headers = default_headers_factory(api_key)
    try:
        resp = get_json(url, headers=headers, timeout=30.0)
    except Exception as exc:
        logger.warning(f"ASR RESTful 查询失败: {exc}")
        return None

    if resp.status_code != HTTPStatus.OK:
        logger.warning(
            f"ASR RESTful 查询失败: status_code={resp.status_code}, body={resp.text[:300]}"
        )
        return None

    data = resp.json()
    if isinstance(data, dict) and isinstance(data.get("output"), dict):
        return data["output"]
    return data if isinstance(data, dict) else None


def transcription_text_from_results(
    *,
    task_id: str,
    output: Any,
    status_code: int | None,
    get_output_value: Callable[[Any, str, Any], Any],
    download_transcription: Callable[[str], Optional[str]],
    log_prefix: str = "",
) -> Optional[str]:
    results = get_output_value(output, "results", []) or []
    status_message = get_output_value(output, "status_message", None)
    logger.info(
        "ASR 任务状态{}: task_id={}, task_status={}, status_code={}, status_message={}, results={}",
        log_prefix,
        task_id,
        get_output_value(output, "task_status", None),
        status_code,
        status_message,
        len(results),
    )
    for item in results:
        sub_status = item.get("subtask_status")
        transcription_url = item.get("transcription_url")
        error_message = item.get("error_message") or item.get("message")
        if sub_status:
            logger.info(
                "ASR 子任务状态{}: task_id={}, subtask_status={}, has_url={}, error={}",
                log_prefix,
                task_id,
                sub_status,
                bool(transcription_url),
                error_message,
            )
        if sub_status == "SUCCEEDED" and transcription_url:
            return download_transcription(transcription_url)
    return None


def transcribe_sync_restful(
    audio_url: str,
    model: str,
    *,
    timeout: int,
    submit_task: Callable[[str, str], Optional[str]],
    fetch_task: Callable[[str], Optional[dict]],
    get_output_value: Callable[[Any, str, Any], Any] = output_value,
    download_transcription: Callable[
        [str], Optional[str]
    ] = download_transcription_text,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> Optional[str]:
    """Run a RESTful DashScope transcription task synchronously."""
    task_id = submit_task(audio_url, model)
    if not task_id:
        logger.warning("ASR RESTful 未返回 task_id")
        return None
    logger.info(f"ASR 任务已提交(RESTful): task_id={task_id}")

    start = now()
    output = None
    while True:
        if now() - start > timeout:
            logger.warning("ASR 任务超时(RESTful)")
            return None
        output = fetch_task(task_id)
        if not output:
            sleep(1.5)
            continue
        status = get_output_value(output, "task_status", None)
        if status in ("SUCCEEDED", "FAILED"):
            break
        sleep(1.5)

    text = transcription_text_from_results(
        task_id=task_id,
        output=output,
        status_code=HTTPStatus.OK,
        get_output_value=get_output_value,
        download_transcription=download_transcription,
        log_prefix="(RESTful)",
    )
    if text:
        return text

    logger.warning("ASR 未返回有效转写结果(RESTful)")
    return None


def transcribe_sync_with_sdk(
    audio_url: str,
    *,
    model: str,
    timeout: int,
    transcription: Any = Transcription,
    get_output_value: Callable[[Any, str, Any], Any] = output_value,
    download_transcription: Callable[
        [str], Optional[str]
    ] = download_transcription_text,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> Optional[str]:
    """Run a DashScope SDK transcription task synchronously."""
    kwargs = {}
    if "paraformer" in model:
        kwargs["language_hints"] = ["zh", "en"]

    try:
        resp = transcription.async_call(
            model=model,
            file_urls=[audio_url],
            **kwargs,
        )
    except Exception as exc:
        logger.warning(f"ASR 提交失败: {exc}")
        return None

    output = getattr(resp, "output", None)
    task_id = get_output_value(output, "task_id", None)
    if not task_id:
        logger.warning("ASR 未返回 task_id")
        return None
    logger.info(f"ASR 任务已提交: task_id={task_id}")

    start = now()
    while True:
        status = get_output_value(output, "task_status", None)
        if status in ("SUCCEEDED", "FAILED"):
            break
        if now() - start > timeout:
            logger.warning("ASR 任务超时")
            return None
        sleep(1.5)
        resp = transcription.fetch(task=task_id)
        output = getattr(resp, "output", None)

    status_code = getattr(resp, "status_code", None)
    if status_code != HTTPStatus.OK:
        logger.warning(f"ASR 请求失败: status_code={status_code}")
        return None

    text = transcription_text_from_results(
        task_id=task_id,
        output=output,
        status_code=status_code,
        get_output_value=get_output_value,
        download_transcription=download_transcription,
    )
    if text:
        return text

    logger.warning("ASR 未返回有效转写结果")
    return None
