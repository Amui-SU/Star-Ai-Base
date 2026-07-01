"""Audio preparation helpers for DashScope ASR."""

from collections.abc import Callable
import os
import shutil
import subprocess
from typing import Optional, Protocol

from loguru import logger


class CommandResult(Protocol):
    returncode: int
    stderr: str | None


FindExecutable = Callable[[str], str | None]
RunCommand = Callable[[list[str]], CommandResult]


def _run_subprocess(cmd: list[str]) -> CommandResult:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def transcode_audio_to_pcm(
    file_path: str,
    *,
    find_executable: FindExecutable = shutil.which,
    run_command: RunCommand = _run_subprocess,
) -> Optional[str]:
    """Transcode an audio file to 16k s16le PCM for Recognition."""
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        logger.info("未检测到 ffmpeg，无法转码为 PCM")
        return None

    base, _ext = os.path.splitext(file_path)
    pcm_path = base + ".pcm"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        file_path,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        pcm_path,
    ]
    try:
        result = run_command(cmd)
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            logger.warning(f"转码 PCM 失败: {err[:200]}")
            return None
        return pcm_path
    except Exception as exc:
        logger.warning(f"转码 PCM 异常: {exc}")
        return None


def transcode_audio_to_wav(
    file_path: str,
    *,
    find_executable: FindExecutable = shutil.which,
    run_command: RunCommand = _run_subprocess,
) -> Optional[str]:
    """Transcode an audio file to 16k mono WAV for Recognition."""
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        logger.info("未检测到 ffmpeg，无法转码为 WAV")
        return None

    base, _ext = os.path.splitext(file_path)
    wav_path = base + ".wav"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        file_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        wav_path,
    ]
    try:
        result = run_command(cmd)
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            logger.warning(f"转码 WAV 失败: {err[:200]}")
            return None
        return wav_path
    except Exception as exc:
        logger.warning(f"转码 WAV 异常: {exc}")
        return None


def prepare_recognition_input(
    file_path: str,
    *,
    input_format: str | None,
    transcode_wav: Callable[[str], Optional[str]] = transcode_audio_to_wav,
    transcode_pcm: Callable[[str], Optional[str]] = transcode_audio_to_pcm,
) -> Optional[str]:
    """Prepare a local file in the configured Recognition input format."""
    fmt = (input_format or "pcm").lower()
    if fmt == "wav":
        return transcode_wav(file_path)
    return transcode_pcm(file_path)
