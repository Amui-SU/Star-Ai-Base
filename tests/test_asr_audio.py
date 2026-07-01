from types import SimpleNamespace

from app.services.asr_audio import (
    prepare_recognition_input,
    transcode_audio_to_pcm,
    transcode_audio_to_wav,
)


def test_transcode_audio_to_pcm_returns_none_when_ffmpeg_missing():
    assert (
        transcode_audio_to_pcm(
            "audio.mp4",
            find_executable=lambda _name: None,
            run_command=lambda _cmd: SimpleNamespace(returncode=0, stderr=""),
        )
        is None
    )


def test_transcode_audio_to_pcm_builds_16k_s16le_command():
    calls = []

    result = transcode_audio_to_pcm(
        "C:/tmp/audio.mp4",
        find_executable=lambda name: f"C:/bin/{name}.exe",
        run_command=lambda cmd: calls.append(cmd)
        or SimpleNamespace(returncode=0, stderr=""),
    )

    assert result == "C:/tmp/audio.pcm"
    assert calls == [
        [
            "C:/bin/ffmpeg.exe",
            "-y",
            "-i",
            "C:/tmp/audio.mp4",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "C:/tmp/audio.pcm",
        ]
    ]


def test_transcode_audio_to_wav_builds_16k_mono_command_and_handles_failure():
    calls = []

    result = transcode_audio_to_wav(
        "C:/tmp/audio.m4a",
        find_executable=lambda name: f"C:/bin/{name}.exe",
        run_command=lambda cmd: calls.append(cmd)
        or SimpleNamespace(returncode=1, stderr="bad codec"),
    )

    assert result is None
    assert calls == [
        [
            "C:/bin/ffmpeg.exe",
            "-y",
            "-i",
            "C:/tmp/audio.m4a",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            "C:/tmp/audio.wav",
        ]
    ]


def test_prepare_recognition_input_uses_configured_format():
    calls = []

    assert (
        prepare_recognition_input(
            "audio.mp4",
            input_format="wav",
            transcode_wav=lambda file_path: calls.append(("wav", file_path))
            or "audio.wav",
            transcode_pcm=lambda file_path: calls.append(("pcm", file_path))
            or "audio.pcm",
        )
        == "audio.wav"
    )
    assert (
        prepare_recognition_input(
            "audio.mp4",
            input_format="pcm",
            transcode_wav=lambda file_path: calls.append(("wav", file_path))
            or "audio.wav",
            transcode_pcm=lambda file_path: calls.append(("pcm", file_path))
            or "audio.pcm",
        )
        == "audio.pcm"
    )

    assert calls == [("wav", "audio.mp4"), ("pcm", "audio.mp4")]
