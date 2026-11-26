#!/usr/bin/env python3
"""Моушн-графика для сцен без картинок: анимированный текст, эквалайзер в такт голосу,
частицы, дрейфующий свет и зерно плёнки. Вызывается из build_video.py.

Поля сцены в project.json:
    card  — текст кадра (перенос строки: \\n), напр. "1980\\nРОСТОВ-НА-ДОНУ" или "35 000"
    anim  — pop | slide | type | count | glitch   (по умолчанию: count, если в card есть число > 99, иначе pop)
"""
import math
import random
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
GOLD = (232, 195, 90)
TEXT_Y = 0.36  # центр текста по высоте (субтитры ниже, интерфейс соцсетей — по краям)
BARS_Y = 1130  # линия эквалайзера


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out_cubic(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def voice_envelope(path) -> np.ndarray | None:
    """Громкость голоса по кадрам (0..1) для эквалайзера."""
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                              "-f", "s16le", "-"], capture_output=True, check=True).stdout
    except Exception:
        return None
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    hop = 16000 // FPS
    n = len(a) // hop
    if n == 0:
        return None
    rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    rms /= np.percentile(rms, 95) + 1e-6
    rms = np.convolve(np.clip(rms, 0, 1.2), np.ones(3) / 3, mode="same")
    return rms


class Background:
    """Тёмный градиент с дрейфующим пятном света и зерном (общий для всех сцен)."""

    def __init__(self, seed=7):
        rng = np.random.default_rng(seed)
        eh = H + 400
        y = np.linspace(0, 1, eh)[:, None]
        x = np.linspace(-1, 1, W)[None, :]
        top, bottom = np.array([38, 14, 12]), np.array([8, 7, 9])
        base = top[None, None, :] * (1 - y[..., None]) + bottom[None, None, :] * y[..., None]
        glow = np.exp(-((x * 1.1) ** 2 + ((y - 0.4) * 2.2) ** 2))[..., None]
        self.big = np.clip(base + glow * np.array([95, 60, 25]), 0, 255).astype(np.int16)
        self.grain = [rng.normal(0, 9, (H, W, 1)).astype(np.int16) for _ in range(6)]

    def frame(self, t, k):
        off = int(200 + 180 * math.sin(t * 0.35))
        img = self.big[off: off + H] + self.grain[k % 6]
        return np.clip(img, 0, 255).astype(np.uint8)


def text_layer(text, font_path, size, color=GOLD, spacing=None):
    font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)
    spacing = spacing if spacing is not None else size // 5
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = (int(round(v)) for v in tmp.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center"))
    pad = 24
    img = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.multiline_text((pad - l + 5, pad - t + 6), text, font=font, fill=(0, 0, 0, 170), spacing=spacing, align="center")
    d.multiline_text((pad - l, pad - t), text, font=font, fill=color + (255,), spacing=spacing, align="center")
    return img


def fit_size(card, font_path, max_w=900, max_h=760):
    """Самый крупный размер шрифта (до 250), при котором текст влезает в кадр."""
    size = 250
    while size > 60:
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)
        l, t, r, b = ImageDraw.Draw(Image.new("RGBA", (1, 1))).multiline_textbbox(
            (0, 0), card, font=font, spacing=size // 5, align="center")
        if r - l <= max_w and b - t <= max_h:
            return size
        size -= 6
    return size


def paste_center(canvas, layer, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BILINEAR)
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    canvas.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def render(card, anim, dur, out, font_path, env=None, t0=0.0, seed=0, bg=None):
    bg = bg or Background()
    rng = random.Random(seed)
    lines = card.split("\n")
    size = fit_size(card, font_path)
    if not anim:
        anim = "count" if re.search(r"\d[\d  ]{2,}", card) else "pop"
    frames = max(1, round(dur * FPS))
    cx, cy = W / 2, H * TEXT_Y

    full = text_layer(card, font_path, size)
    line_layers = [text_layer(l, font_path, size) for l in lines]
    line_h = full.height / max(len(lines), 1)

    num_match = re.search(r"\d[\d  ]*\d|\d", card)
    target = int(re.sub(r"\D", "", num_match.group())) if num_match else 0

    parts = [[rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.5, 4.5), rng.uniform(20, 70), rng.uniform(0, 6.28)]
             for _ in range(55)]
    bars, phases = 23, [rng.uniform(0, 6.28) for _ in range(23)]

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "18", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for f in range(frames):
        t = f / FPS
        gt = t0 + t
        canvas = Image.fromarray(bg.frame(gt, f)).convert("RGBA")
        d = ImageDraw.Draw(canvas)

        # частицы-пылинки, поднимаются вверх
        for p in parts:
            x = (p[0] + 25 * math.sin(gt * 0.8 + p[4])) % W
            y = (p[1] - p[3] * gt) % H
            a = int(90 + 80 * math.sin(gt * 2 + p[4]))
            d.ellipse((x - p[2], y - p[2], x + p[2], y + p[2]), fill=(255, 210, 140, max(a, 20)))

        # эквалайзер в такт голосу (зеркальный)
        level = 0.25
        if env is not None and len(env):
            level = float(env[min(int(gt * FPS), len(env) - 1)])
        bw, gap = 22, 14
        x0 = cx - (bars * (bw + gap) - gap) / 2
        for i in range(bars):
            shape = 0.35 + 0.65 * abs(math.sin(gt * 7 + phases[i])) * (1 - abs(i - bars // 2) / (bars * 0.75))
            h = 10 + 150 * level * shape
            x = x0 + i * (bw + gap)
            d.rounded_rectangle((x, BARS_Y - h, x + bw, BARS_Y + h * 0.45), radius=6,
                                fill=GOLD + (int(110 + 120 * min(level, 1)),))

        # анимация текста
        intro = t / 0.45
        breathe = 1 + 0.025 * math.sin(t * 2.2)
        if anim == "slide":
            top = cy - full.height / 2 + line_h / 2
            for i, layer in enumerate(line_layers):
                k = ease_out_cubic((t - i * 0.18) / 0.5)
                side = -1 if i % 2 == 0 else 1
                paste_center(canvas, layer, cx + side * (1 - k) * W * 0.9, top + i * line_h, 1.0, k)
        elif anim == "type":
            n = len(card)
            shown = card[: max(0, min(n, int(n * t / max(dur * 0.45, 0.4))))]
            if shown.strip():
                lay = text_layer(shown + ("▍" if int(t * 3) % 2 == 0 and len(shown) < n else ""), font_path, size)
                paste_center(canvas, lay, cx, cy)
        elif anim == "count" and num_match:
            k = ease_out_cubic(t / max(dur * 0.6, 0.5))
            val = f"{int(target * k):,}".replace(",", " ")
            text = card[: num_match.start()] + val + card[num_match.end():]
            lay = text_layer(text, font_path, size)
            pulse = 1 + (0.08 * math.exp(-(t - dur * 0.6) * 6) if t >= dur * 0.6 else 0)
            paste_center(canvas, lay, cx, cy, pulse * min(1, 0.7 + 0.3 * ease_out_cubic(intro)))
        elif anim == "glitch":
            if t < 0.5 and rng.random() < 0.7:
                for dx, col in ((-14, (255, 40, 60)), (14, (40, 200, 255))):
                    paste_center(canvas, text_layer(card, font_path, size, col), cx + dx + rng.uniform(-8, 8),
                                 cy + rng.uniform(-6, 6), 1.0, 0.6)
            paste_center(canvas, full, cx + (rng.uniform(-10, 10) if t < 0.5 else 0), cy, breathe)
        else:  # pop
            paste_center(canvas, full, cx, cy, ease_out_back(intro) * breathe, min(1, intro * 2))

        # золотая линия под текстом раскрывается из центра
        k = ease_out_cubic((t - 0.15) / 0.5)
        if k > 0:
            ly = cy + full.height / 2 + 18
            half = 260 * k
            d = ImageDraw.Draw(canvas)
            d.rectangle((cx - half, ly, cx + half, ly + 5), fill=GOLD + (230,))

        # вспышка на смене сцены
        if t < 0.15:
            flash = Image.new("RGBA", (W, H), (255, 240, 210, int(150 * (1 - t / 0.15))))
            canvas.alpha_composite(flash)

        proc.stdin.write(canvas.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg не смог записать {out}")
    return out
