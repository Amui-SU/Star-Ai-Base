"""
Bilibili RAG 知识库系统

ASR 服务 - 使用 DashScope 录音文件识别
"""

import asyncio
import os
from typing import Optional, Any
from urllib import request as urlrequest

import dashscope
from dashscope.audio.asr import Recognition
from dashscope.utils.oss_utils import OssUtils
from loguru import logger

from app.config import settings
from app.services.asr_audio import (
    prepare_recognition_input,
    transcode_audio_to_pcm,
    transcode_audio_to_wav,
)
from app.services.asr_transcription import (
    build_dashscope_api_url,
    download_transcription_text,
    fetch_transcription_task_restful,
    submit_transcription_task_restful,
    transcribe_sync_restful,
    transcribe_sync_with_sdk,
)


class ASRService:
    """音频转文字服务（DashScope）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or settings.dashscope_api_key
        self.base_url = base_url or getattr(settings, "dashscope_base_url", None)
        self.model = model or getattr(settings, "asr_model", "fun-asr")
        self.timeout = timeout or getattr(settings, "asr_timeout", 600)
        self.local_model = getattr(settings, "asr_model_local", self.model)
        self.input_format = getattr(settings, "asr_input_format", "pcm")

    def _configure(self) -> None:
        if not self.api_key:
            raise ValueError("未配置 DASHSCOPE API Key")
        dashscope.api_key = self.api_key
        if self.base_url:
            dashscope.base_http_api_url = self.base_url

    def _get_output_value(self, output: Any, key: str, default=None):
        if isinstance(output, dict):
            return output.get(key, default)
        return getattr(output, key, default)

    def _transcode_audio_to_pcm(self, file_path: str) -> Optional[str]:
        """转码为 16k s16le PCM，适配 Recognition"""
        return transcode_audio_to_pcm(file_path)

    def _transcode_audio_to_wav(self, file_path: str) -> Optional[str]:
        """转码为 16k 单声道 WAV"""
        return transcode_audio_to_wav(file_path)

    def _prepare_recognition_input(self, file_path: str) -> Optional[str]:
        """按输入格式准备 Recognition 文件"""
        return prepare_recognition_input(
            file_path,
            input_format=self.input_format,
            transcode_wav=self._transcode_audio_to_wav,
            transcode_pcm=self._transcode_audio_to_pcm,
        )

    def _recognize_local_file(self, file_path: str) -> Optional[str]:
        """使用 Recognition 直传本地音频"""
        self._configure()
        if not os.path.exists(file_path):
            logger.warning(f"ASR 本地文件不存在: {file_path}")
            return None

        input_path = self._prepare_recognition_input(file_path)
        if not input_path:
            return None

        logger.info(
            f"ASR Recognition 使用模型: {self.local_model or self.model}, format={self.input_format or 'pcm'}"
        )

        try:
            recognizer = Recognition(
                model=self.local_model or self.model,
                callback=None,
                format=(self.input_format or "pcm"),
                sample_rate=16000,
            )
            result = recognizer.call(input_path)
            logger.info(
                "ASR Recognition 结果: status_code={}, code={}, message={}, request_id={}",
                getattr(result, "status_code", None),
                getattr(result, "code", None),
                getattr(result, "message", None),
                getattr(result, "request_id", None),
            )
            sentences = result.get_sentence() or []
            if isinstance(sentences, dict):
                sentences = [sentences]
            texts = []
            for s in sentences:
                if isinstance(s, dict):
                    t = s.get("text") or ""
                    if t:
                        texts.append(t)
            text = "\n".join(texts).strip() if texts else None
            if text:
                preview = text[:120].replace("\n", " ").strip()
                logger.info(f"ASR Recognition 成功，长度={len(text)}，预览：{preview}")
            return text
        except Exception as e:
            logger.warning(f"ASR Recognition 异常: {e}")
            return None
        finally:
            for path in {file_path, input_path}:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except Exception:
                    logger.debug(f"ASR 临时文件清理失败: {path}")

    def _download_transcription(self, url: str) -> Optional[str]:
        return download_transcription_text(url, open_url=urlrequest.urlopen)

    def _build_api_url(self, *parts: str) -> str:
        return build_dashscope_api_url(*parts, base_url=self.base_url)

    def _submit_transcription_task_restful(
        self, audio_url: str, model: str
    ) -> Optional[str]:
        return submit_transcription_task_restful(
            audio_url,
            model,
            api_key=self.api_key,
            build_api_url=self._build_api_url,
        )

    def _fetch_transcription_task_restful(self, task_id: str) -> Optional[dict]:
        return fetch_transcription_task_restful(
            task_id,
            api_key=self.api_key,
            build_api_url=self._build_api_url,
        )

    def _transcribe_sync_restful(self, audio_url: str, model: str) -> Optional[str]:
        self._configure()
        return transcribe_sync_restful(
            audio_url,
            model,
            timeout=self.timeout,
            submit_task=self._submit_transcription_task_restful,
            fetch_task=self._fetch_transcription_task_restful,
            get_output_value=self._get_output_value,
            download_transcription=self._download_transcription,
        )

    def _transcribe_sync(self, audio_url: str) -> Optional[str]:
        self._configure()
        if audio_url.startswith("oss://"):
            return self._transcribe_sync_restful(audio_url, self.model)
        return transcribe_sync_with_sdk(
            audio_url,
            model=self.model,
            timeout=self.timeout,
            get_output_value=self._get_output_value,
            download_transcription=self._download_transcription,
        )

    def _upload_temp_file(
        self, file_path: str, model: Optional[str] = None
    ) -> Optional[str]:
        """上传本地文件到 DashScope 临时 OSS，返回 oss:// URL"""
        self._configure()
        if not os.path.exists(file_path):
            logger.warning(f"ASR 本地文件不存在: {file_path}")
            return None
        try:
            upload_model = model or self.local_model or self.model
            oss_url = OssUtils.upload(
                model=upload_model,
                file_path=file_path,
                api_key=self.api_key,
            )
            logger.info(f"ASR 临时文件上传成功: {oss_url}")
            return oss_url
        except Exception as e:
            logger.warning(f"ASR 临时文件上传失败: {e}")
            return None

    async def transcribe_url(self, audio_url: str) -> Optional[str]:
        return await asyncio.to_thread(self._transcribe_sync, audio_url)

    async def transcribe_local_file(self, file_path: str) -> Optional[str]:
        """本地文件直传识别（Recognition）"""
        return await asyncio.to_thread(self._recognize_local_file, file_path)

    def _transcribe_sync_with_model(self, audio_url: str, model: str) -> Optional[str]:
        """使用指定模型转写（用于本地文件上传）"""
        if audio_url.startswith("oss://"):
            return self._transcribe_sync_restful(audio_url, model)
        original_model = self.model
        try:
            self.model = model
            return self._transcribe_sync(audio_url)
        finally:
            self.model = original_model
