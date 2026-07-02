"""Local audio preparation helpers for content fetching."""

from collections.abc import Callable
import math
import os
import shutil
import subprocess
from typing import Optional, Protocol

from loguru import logger


class CommandResult(Protocol):
    returncode: int
    stderr: str | None
    stdout: str | None


FindExecutable = Callable[[str], str | None]
RunCommand = Callable[[list[str]], CommandResult]


def _run_subprocess(cmd: list[str]) -> CommandResult:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def transcode_audio_to_wav(
    bvid: str,
    file_path: str,
    *,
    find_executable: FindExecutable = shutil.which,
    run_command: RunCommand = _run_subprocess,
    path_exists: Callable[[str], bool] = os.path.exists,
    get_file_size: Callable[[str], int] = os.path.getsize,
) -> Optional[str]:
    """Transcode local audio to 16k mono WAV for ASR compatibility."""
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        logger.info(f"[{bvid}] 未检测到 ffmpeg，跳过转码")
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
            logger.info(f"[{bvid}] ffmpeg 转码失败: {err[:300]}")
            return None
    except Exception as e:
        logger.info(f"[{bvid}] ffmpeg 转码异常: {e}")
        return None

    if not path_exists(wav_path) or get_file_size(wav_path) < 1024:
        logger.info(f"[{bvid}] 转码输出过小，跳过使用 wav")
        return None

    logger.info(f"[{bvid}] 转码完成，使用 wav 上传: {wav_path}")
    return wav_path


def get_audio_duration_sec(
    file_path: str,
    *,
    find_executable: FindExecutable = shutil.which,
    run_command: RunCommand = _run_subprocess,
) -> Optional[float]:
    ffprobe = find_executable("ffprobe")
    if not ffprobe:
        return None
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        result = run_command(cmd)
        if result.returncode != 0:
            return None
        value = (result.stdout or "").strip()
        return float(value) if value else None
    except Exception:
        return None


def split_audio_wav(
    bvid: str,
    wav_path: str,
    segment_seconds: int = 1200,
    *,
    find_executable: FindExecutable = shutil.which,
    duration_reader: Callable[[str], Optional[float]] = get_audio_duration_sec,
    run_command: RunCommand = _run_subprocess,
    path_exists: Callable[[str], bool] = os.path.exists,
    get_file_size: Callable[[str], int] = os.path.getsize,
    remove_file: Callable[[str], None] = os.remove,
) -> list[str]:
    """Split a long WAV file into shorter 16k mono segments."""
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        logger.info(f"[{bvid}] 未检测到 ffmpeg，跳过切分")
        return [wav_path]

    duration = duration_reader(wav_path)
    if not duration or duration <= segment_seconds:
        return [wav_path]

    total_segments = int(math.ceil(duration / segment_seconds))
    logger.info(f"[{bvid}] 音频较长({duration:.1f}s)，切分为 {total_segments} 段")

    base, _ext = os.path.splitext(wav_path)
    segment_paths: list[str] = []
    for idx in range(total_segments):
        start = idx * segment_seconds
        out_path = f"{base}_part{idx + 1:03d}.wav"
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            wav_path,
            "-ss",
            str(start),
            "-t",
            str(segment_seconds),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            out_path,
        ]
        try:
            result = run_command(cmd)
            if result.returncode != 0:
                err = (result.stderr or "").strip()
                logger.info(f"[{bvid}] 切分失败: {err[:300]}")
                continue
        except Exception as e:
            logger.info(f"[{bvid}] 切分异常: {e}")
            continue

        if path_exists(out_path) and get_file_size(out_path) >= 1024:
            segment_paths.append(out_path)

    if not segment_paths:
        return [wav_path]

    try:
        remove_file(wav_path)
    except Exception:
        logger.debug(f"[{bvid}] 清理原始 wav 失败: {wav_path}")

    return segment_paths
