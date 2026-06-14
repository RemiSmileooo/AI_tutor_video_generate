"""视频合成：把每个讲解片段的(画面 + 音频)按顺序拼接为完整 MP4。

每个片段是一张静态画面 + 一段配音，画面时长 = 配音时长，
因此整段视频就是片段的顺序拼接，稳定可靠。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .config import settings
from .models import Course


def _subclip(audio, start: float, end: float):
    """兼容 moviepy 2.x(subclipped) 与 1.x(subclip)。"""
    if hasattr(audio, "subclipped"):
        return audio.subclipped(start, end)
    return audio.subclip(start, end)


def compose_course(
    course: Course,
    out_path: str | Path,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str):
        if progress_cb:
            progress_cb(msg)

    clips = []
    audios = []
    total = sum(len(s.segments) for s in course.slides)
    done = 0

    for slide in course.slides:
        for seg in slide.segments:
            if not seg.audio_path or not seg.captions:
                continue
            audio = AudioFileClip(seg.audio_path)
            audios.append(audio)
            seg_dur = float(audio.duration)  # 以真实音频时长为准，避免越界

            for cap in seg.captions:
                if not cap.frame_path:
                    continue
                start = max(0.0, min(cap.start, seg_dur))
                end = min(cap.start + cap.duration, seg_dur - 1e-3)
                if end <= start:
                    continue
                sub_audio = _subclip(audio, start, end)
                clip = (
                    ImageClip(cap.frame_path)
                    .with_duration(end - start)
                    .with_audio(sub_audio)
                    .with_fps(settings.fps)
                )
                clips.append(clip)
            done += 1
            log(f"合成片段 {done}/{total}")

    if not clips:
        raise RuntimeError("没有可合成的片段")

    final = concatenate_videoclips(clips, method="chain")
    log("写出 MP4（编码中）…")
    final.write_videofile(
        str(out_path),
        fps=settings.fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
        logger=None,
    )

    final.close()
    for a in audios:
        try:
            a.close()
        except Exception:
            pass
    return str(out_path)
