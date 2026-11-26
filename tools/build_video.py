#!/usr/bin/env python3
"""Сборка вертикального ролика 1080x1920 из сцен, озвучки, музыки и субтитров.

Использование:
    python tools/build_video.py projects/<slug> [--no-subs] [--music путь.mp3]

Ожидает projects/<slug>/project.json (см. templates/project.json):
    scenes[]: image (картинка .png/.jpg или клип .mp4/.mov), text,
              duration (необязательно, сек), motion: in|out|left|right|none
Необязательно: voice.mp3, subs.srt, music.mp3 в папке проекта.
Если картинки ещё нет — подставляется заглушка «СЦЕНА N», чтобы проверить тайминг.
Результат: projects/<slug>/out/final.mp4
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

W, H, FPS = 1080, 1920, 30
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
MOTIONS = ["in", "out", "left", "right"]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Ошибка ffmpeg:\n{' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def duration_of(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def find_font() -> str | None:
    if shutil.which("fc-match"):
        r = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"], capture_output=True, text=True)
        if r.returncode == 0 and Path(r.stdout).exists():
            return r.stdout
    return None


def plan_durations(scenes, total: float):
    """Длительность сцен пропорционально длине текста, минимум 1.5 с, в сумме = total."""
    durs = [float(s["duration"]) if s.get("duration") else None for s in scenes]
    weights = [max(len(s.get("text", "")), 1) for s in scenes]
    while True:
        free = [i for i, d in enumerate(durs) if d is None]
        if not free:
            return durs
        rest = max(total - sum(d for d in durs if d is not None), 1.5 * len(free))
        wsum = sum(weights[i] for i in free)
        short = [i for i in free if rest * weights[i] / wsum < 1.5]
        if not short:
            for i in free:
                durs[i] = rest * weights[i] / wsum
            return durs
        for i in short:
            durs[i] = 1.5


def motion_filter(motion: str, frames: int) -> str:
    n = max(frames - 1, 1)
    center = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if motion == "in":
        z, xy = f"1+0.15*on/{n}", center
    elif motion == "out":
        z, xy = f"1.15-0.15*on/{n}", center
    elif motion == "left":
        z, xy = "1.15", f"x='(iw-iw/zoom)*(1-on/{n})':y='ih/2-(ih/zoom/2)'"
    elif motion == "right":
        z, xy = "1.15", f"x='(iw-iw/zoom)*on/{n}':y='ih/2-(ih/zoom/2)'"
    else:
        z, xy = "1", center
    cover = f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2}"
    return f"{cover},zoompan=z='{z}':{xy}:d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p"


def render_scene(i, scene, dur, project: Path, tmp: Path, font):
    out = tmp / f"scene_{i:02}.mp4"
    frames = round(dur * FPS)
    src = project / scene.get("image", "")
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), "-an"]
    if scene.get("image") and src.exists() and src.suffix.lower() in VIDEO_EXT:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},format=yuv420p"
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src, "-t", f"{dur:.3f}", "-vf", vf, *enc, out])
    elif scene.get("image") and src.exists():
        motion = scene.get("motion") or MOTIONS[i % len(MOTIONS)]
        run(["ffmpeg", "-y", "-loop", "1", "-i", src, "-frames:v", str(frames),
             "-vf", motion_filter(motion, frames), *enc, out])
    else:
        label = f"СЦЕНА {i + 1}"
        vf = "format=yuv420p"
        if font:
            vf = (f"drawtext=fontfile='{font}':text='{label}':fontcolor=0xC9A227:fontsize=110:"
                  f"x=(w-tw)/2:y=(h-th)/2,format=yuv420p")
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x15110c:s={W}x{H}:r={FPS}",
             "-frames:v", str(frames), "-vf", vf, *enc, out])
        print(f"  сцена {i + 1}: нет файла «{scene.get('image', '')}» — заглушка")
    return out


def ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def auto_srt(scenes, durs, per_line=3) -> str:
    """Субтитры из текста сцен, если нет subs.srt (тайминг приблизительный)."""
    entries, t = [], 0.0
    for s, d in zip(scenes, durs):
        words = s.get("text", "").split()
        chunks = [words[k:k + per_line] for k in range(0, len(words), per_line)]
        total = sum(len(" ".join(c)) for c in chunks) or 1
        for c in chunks:
            piece = d * len(" ".join(c)) / total
            entries.append((t, t + piece, " ".join(c).upper()))
            t += piece
        if not chunks:
            t += d
    return "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(entries, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--no-subs", action="store_true", help="не вшивать субтитры")
    ap.add_argument("--music", type=Path, help="фоновая музыка (по умолчанию music.mp3 в проекте)")
    ap.add_argument("--music-volume", type=float, default=0.15)
    a = ap.parse_args()

    project = a.project.resolve()
    cfg = json.loads((project / "project.json").read_text(encoding="utf-8"))
    scenes = cfg["scenes"]
    voice = project / "voice.mp3"
    music = a.music.resolve() if a.music else project / "music.mp3"

    total = duration_of(voice) + 0.8 if voice.exists() else sum(s.get("duration", 5) for s in scenes)
    durs = plan_durations(scenes, total)
    print(f"Сцен: {len(scenes)}, длительность: {sum(durs):.1f} с")

    tmp = project / "out" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    font = find_font()
    clips = [render_scene(i, s, d, project, tmp, font) for i, (s, d) in enumerate(zip(scenes, durs))]
    (tmp / "list.txt").write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4"], cwd=tmp)

    # Субтитры
    vf = []
    if not a.no_subs:
        srt = project / "subs.srt"
        if not srt.exists():
            srt = tmp / "subs_auto.srt"
            srt.write_text(auto_srt(scenes, durs), encoding="utf-8")
        shutil.copy(srt, tmp / "subs.srt")
        style = ("FontName=DejaVu Sans,Bold=1,FontSize=13,PrimaryColour=&H00FFFFFF,"
                 "OutlineColour=&H00000000,BorderStyle=1,Outline=1.6,Shadow=0,Alignment=2,MarginV=80")
        vf = ["-vf", f"subtitles=subs.srt:force_style='{style}'"]

    # Звук: голос + музыка тише, общая громкость под соцсети (-14 LUFS)
    inputs, filters, n = ["-i", "video.mp4"], [], 1
    if voice.exists():
        inputs += ["-i", str(voice)]
        filters.append(f"[{n}:a]volume=1.0[v]")
        n += 1
    if music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fade = max(sum(durs) - 2, 0)
        filters.append(f"[{n}:a]volume={a.music_volume},afade=t=out:st={fade:.2f}:d=2[m]")
        n += 1
    labels = "".join(x for x, ok in (("[v]", voice.exists()), ("[m]", music.exists())) if ok)
    audio = []
    if labels:
        k = labels.count("[")
        mix = f"{labels}amix=inputs={k}:duration=longest:normalize=0," if k > 1 else f"{labels}"
        filters.append(f"{mix}loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        audio = ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]",
                 "-c:a", "aac", "-b:a", "192k"]
    else:
        audio = ["-map", "0:v"]

    final = project / "out" / "final.mp4"
    run(["ffmpeg", "-y", *inputs, *audio, *vf, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-t", f"{sum(durs):.3f}", "-movflags", "+faststart", str(final)], cwd=tmp)
    print(f"Готово: {final}")


if __name__ == "__main__":
    main()
