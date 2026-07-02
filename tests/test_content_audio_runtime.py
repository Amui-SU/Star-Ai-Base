from types import SimpleNamespace

from app.services.content_audio_runtime import (
    get_audio_duration_sec,
    split_audio_wav,
    transcode_audio_to_wav,
)


def test_transcode_audio_to_wav_builds_16k_mono_command_and_validates_output():
    calls = []

    result = transcode_audio_to_wav(
        "BV1AUDIO",
        "C:/tmp/audio.m4s",
        find_executable=lambda name: f"C:/bin/{name}.exe",
        run_command=lambda cmd: calls.append(cmd)
        or SimpleNamespace(returncode=0, stderr=""),
        path_exists=lambda path: path == "C:/tmp/audio.wav",
        get_file_size=lambda _path: 4096,
    )

    assert result == "C:/tmp/audio.wav"
    assert calls == [
        [
            "C:/bin/ffmpeg.exe",
            "-y",
            "-i",
            "C:/tmp/audio.m4s",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            "C:/tmp/audio.wav",
        ]
    ]


def test_get_audio_duration_sec_parses_ffprobe_output():
    calls = []

    result = get_audio_duration_sec(
        "C:/tmp/audio.wav",
        find_executable=lambda name: f"C:/bin/{name}.exe",
        run_command=lambda cmd: calls.append(cmd)
        or SimpleNamespace(returncode=0, stdout="42.5\n", stderr=""),
    )

    assert result == 42.5
    assert calls == [
        [
            "C:/bin/ffprobe.exe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            "C:/tmp/audio.wav",
        ]
    ]


def test_split_audio_wav_splits_long_files_and_removes_original():
    calls = []
    removed = []
    existing = {
        "C:/tmp/audio_part001.wav",
        "C:/tmp/audio_part002.wav",
        "C:/tmp/audio_part003.wav",
    }

    result = split_audio_wav(
        "BV1LONG",
        "C:/tmp/audio.wav",
        segment_seconds=1200,
        find_executable=lambda name: f"C:/bin/{name}.exe",
        duration_reader=lambda _path: 2501.0,
        run_command=lambda cmd: calls.append(cmd)
        or SimpleNamespace(returncode=0, stderr=""),
        path_exists=lambda path: path in existing,
        get_file_size=lambda _path: 4096,
        remove_file=removed.append,
    )

    assert result == [
        "C:/tmp/audio_part001.wav",
        "C:/tmp/audio_part002.wav",
        "C:/tmp/audio_part003.wav",
    ]
    assert [cmd[cmd.index("-ss") + 1] for cmd in calls] == ["0", "1200", "2400"]
    assert removed == ["C:/tmp/audio.wav"]
