# claude-1 — сборка скиллов Claude для AI-роликов «история за 60 секунд»

Набор скиллов для [Claude Code](https://claude.com/claude-code), который проводит от идеи до готового вертикального ролика в духе «История старого бога за минуту»: сценарий, единый образ персонажа, промпты для картинок и видео, озвучка, субтитры, монтаж и текст для публикации.

## Что внутри

| Скилл | Что делает |
|---|---|
| `myth-short` | Главный: ведёт по 7 шагам с остановками на одобрение |
| `story-script` | Сценарий на 45–60 с: крючок → завязка → эскалация → кульминация → петля |
| `character-bible` | Фиксирует внешность персонажа и стиль, чтобы бог выглядел одинаково во всех кадрах |
| `scene-prompts` | Промпты для Midjourney / Leonardo / Flux / ChatGPT и Kling / Runway / Seedance / Veo + `project.json` |
| `voiceover` | Бесплатная озвучка (edge-tts) или ElevenLabs, субтитры по словам, словарь ударений |
| `video-assembly` | Сборка 1080×1920 в ffmpeg: движение камеры, субтитры, музыка, громкость −14 LUFS |
| `publish-pack` | Названия, обложка, описание, хэштеги, закреплённый комментарий, идеи серии |

```
.claude/skills/      скиллы
tools/tts.py         озвучка + субтитры
tools/build_video.py сборка видео
templates/           шаблон project.json
pronunciations.txt   словарь ударений для имён богов
projects/<slug>/     папка каждого ролика
```

## Установка

1. Установите [Claude Code](https://claude.com/claude-code), Python 3.10+ и ffmpeg
   (Windows: `winget install ffmpeg`, macOS: `brew install ffmpeg`, Linux: `sudo apt install ffmpeg`).
2. Скачайте репозиторий и установите зависимости:
   ```bash
   git clone https://github.com/markkatkalo75-commits/claude-1.git
   cd claude-1
   pip install -r tools/requirements.txt
   ```
3. Запустите `claude` в этой папке — скиллы подключатся автоматически.

## Как пользоваться

Напишите Claude, например:

> Сделай ролик: история Кроноса за 60 секунд, тёмная эпика

Дальше Claude сам проведёт по шагам:
1. тема и угол подачи → 2. сценарий → 3. персонаж и промпты → 4. **вы** генерируете картинки по промптам и кладёте их в `projects/<slug>/images/` → 5. озвучка → 6. сборка `out/final.mp4` → 7. текст для публикации.

Можно собрать черновик и без картинок — вместо них будут заглушки «СЦЕНА N», чтобы проверить тайминг.

### Вручную, без Claude
```bash
python tools/tts.py projects/kronos          # script.txt → voice.mp3 + subs.srt
python tools/build_video.py projects/kronos  # → projects/kronos/out/final.mp4
```

## Что платно, а что нет
- **Бесплатно:** скиллы, озвучка edge-tts, сборка ffmpeg.
- **На ваш выбор:** генераторы картинок и видео (у многих есть бесплатные лимиты), ElevenLabs для более живого голоса.
- Музыку берите только с разрешённой лицензией (YouTube Audio Library, Pixabay Music).

## Источники идей
Сборка вдохновлена открытыми проектами: [claude-faceless-shorts-creator](https://github.com/hassancs91/claude-faceless-shorts-creator), [claude-youtube](https://github.com/AgriciDaniel/claude-youtube), [awesome-claude-video-skills](https://github.com/zhuyansen/awesome-claude-video-skills). Код этих проектов не копировался.
