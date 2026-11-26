---
name: character-bible
description: Создаёт «библию персонажа и стиля» — неизменное описание главного героя и визуального стиля, чтобы бог/герой выглядел одинаково во всех сценах ролика. Используй перед написанием промптов для картинок.
---

# Библия персонажа и стиля → `projects/<slug>/character.md`

Главная беда AI-роликов — персонаж меняется от кадра к кадру. Решение: один раз зафиксировать описание и **дословно** вставлять его в каждый промпт.

## 1. Персонаж (CHARACTER LOCK)
Одна строка на английском, 25–45 слов, только видимые признаки:
возраст и телосложение · лицо (борода, глаза, шрамы) · волосы · одежда и материалы · главный атрибут (серп, копьё, анкх) · одна уникальная примета.

Пример:
```
CHARACTER: Kronos, ancient titan, gaunt elderly giant, long tangled silver beard, sunken glowing amber eyes, cracked grey skin like dry stone, tattered dark bronze robe, holding a huge curved iron sickle, crown of broken stone
```
Если персонажей несколько — по строке на каждого (не больше 3 на ролик).

## 2. Стиль (STYLE LOCK)
Одна строка, одинаковая для всех сцен: техника, свет, палитра, настроение.
Готовые варианты:
- **Тёмная эпика:** `dark epic fantasy oil painting, dramatic chiaroscuro lighting, muted gold and deep teal palette, volumetric fog, highly detailed, cinematic`
- **Древняя фреска:** `ancient greek fresco style, cracked plaster texture, terracotta and ochre palette, flat figures, museum artifact look`
- **Кинореализм:** `photorealistic cinematic still, 35mm film, anamorphic lens, moody low-key lighting, film grain`
- **Гравюра:** `old engraving illustration, black ink crosshatching on aged parchment, sepia`

## 3. Технические правила
- Формат: `vertical 9:16` (Midjourney: `--ar 9:16`).
- Минус-промпт (где поддерживается): `text, watermark, logo, extra fingers, deformed hands, modern objects, blurry`.
- Сначала сгенерируй **референс персонажа** (портрет в полный рост на нейтральном фоне) и используй его в каждой сцене:
  Midjourney `--cref <url> --cw 80`, Leonardo «Character Reference», Kling/Runway/Seedance — режим «image to video» с этим кадром, ChatGPT/Flux Kontext — прикладывай референс и пиши «same character».
- Зафиксируй seed, если сервис позволяет.

## Формат файла
```
# Персонаж и стиль: <тема>
CHARACTER: ...
(второй персонаж, если есть)
STYLE: ...
FORMAT: vertical 9:16
NEGATIVE: ...
Референс: images/ref.png (сгенерировать первым)
```
