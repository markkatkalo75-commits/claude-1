#!/usr/bin/env python3
"""Бесплатная озвучка через edge-tts + субтитры по словам.

Использование:
    python tools/tts.py projects/<slug>

Читает  projects/<slug>/script.txt  (только текст для диктора)
Пишет   projects/<slug>/voice.mp3, subs.srt и words.json (время слов)

Ударения и произношение: файл pronunciations.txt в корне репозитория
и/или в папке проекта, строки вида  «Один = Óдин»  или  «Локи = Ло́ки».
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

try:
    import edge_tts
except ImportError:
    sys.exit("Не установлен edge-tts: pip install -r tools/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent


def load_pronunciations(project: Path) -> dict[str, str]:
    table: dict[str, str] = {}
    for f in (ROOT / "pronunciations.txt", project / "pronunciations.txt"):
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            src, dst = (p.strip() for p in line.split("=", 1))
            if src and dst:
                table[src] = dst
    return table


def apply_pronunciations(text: str, table: dict[str, str]) -> str:
    for src, dst in sorted(table.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, text)
    return text


def ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def words_to_srt(words: list[tuple[float, float, str]], per_line: int) -> str:
    """Группирует слова по per_line, рвёт группу на знаках препинания."""
    out, group = [], []
    for w in words:
        group.append(w)
        if len(group) >= per_line or re.search(r"[.!?…,:;—]$", w[2]):
            out.append(group)
            group = []
    if group:
        out.append(group)
    lines = []
    for i, g in enumerate(out, 1):
        start, end = g[0][0], g[-1][1]
        text = " ".join(x[2] for x in g).upper()
        lines.append(f"{i}\n{ts(start)} --> {ts(end)}\n{text}\n")
    return "\n".join(lines)


async def synth(text, voice, rate, pitch, mp3: Path):
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    words = []
    with mp3.open("wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                end = start + chunk["duration"] / 1e7
                words.append((start, end, chunk["text"]))
    return words


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--voice", default="ru-RU-DmitryNeural",
                    help="ru-RU-DmitryNeural (муж.) или ru-RU-SvetlanaNeural (жен.)")
    ap.add_argument("--rate", default="-5%", help="скорость, напр. -10%%, +0%%")
    ap.add_argument("--pitch", default="-6Hz", help="высота, ниже = эпичнее")
    ap.add_argument("--words", type=int, default=3, help="слов в одном субтитре")
    a = ap.parse_args()

    script = a.project / "script.txt"
    if not script.exists():
        sys.exit(f"Нет файла {script}")
    raw = script.read_text(encoding="utf-8").strip()
    text = apply_pronunciations(raw, load_pronunciations(a.project))

    mp3 = a.project / "voice.mp3"
    for attempt in range(1, 6):  # сервис иногда отвечает пусто — повторяем
        try:
            words = asyncio.run(synth(text, a.voice, a.rate, a.pitch, mp3))
            break
        except edge_tts.exceptions.NoAudioReceived:
            if attempt == 5:
                sys.exit("Сервис озвучки не ответил 5 раз подряд. Попробуйте позже.")
            print(f"Пустой ответ сервиса, повтор {attempt}/4…")
            time.sleep(2 * attempt)
    # В субтитрах показываем слова без знаков ударения
    words = [(s, e, w.replace("́", "")) for s, e, w in words]
    (a.project / "subs.srt").write_text(words_to_srt(words, a.words), encoding="utf-8")
    # точное время слов — по нему build_video.py меняет сцены синхронно с речью
    (a.project / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    dur = words[-1][1] if words else 0
    print(f"OK: {mp3} ({dur:.1f} с), субтитры: {a.project / 'subs.srt'}")
    if dur > 59:
        print("ВНИМАНИЕ: озвучка длиннее 59 с — сократите текст или поднимите --rate")


if __name__ == "__main__":
    main()
