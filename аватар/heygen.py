"""Аватар HeyGen: точные настройки вызова и проверка темпа. Mac и Windows, только стандартная библиотека.

Коннектор HeyGen вызывает Claude, а настройки берёт отсюда. Руками их не собирай: без явного движка голоса HeyGen сам выбирает
движок для клона, и кыргызский выходит с акцентом (было у двух учеников подряд).

  py heygen.py parametry --avatar LOOK_ID --voice VOICE_ID [--lang ky] [--format vertical|horizontal]
                         [--dvizhok iii|iv|v|6] [--skorost 1.2] [--papka ПАПКА_РОЛИКА] [--tekst сценарий.txt]
        → JSON для create_video_from_avatar. С --papka ещё и ПАПКА/heygen.json (что заказали, для истории).
        Без --tekst поле script пустое: Claude вставляет утверждённый текст дословно.
  py heygen.py temp ФАЙЛ.srt [--lang ky]
        → слов в секунду по субтитрам HeyGen и вердикт: темп нормальный или ускорить на монтаже (команда ffmpeg).

Проверено 16.11.2026 по get_video_voice_capabilities: для кыргызского (ky) у HeyGen есть только движок elevenlabs,
модели eleven_v3 и eleven_v4, без акцента-locale. eleven_v4 звучит живее v3 (наша проверка 21.10.2026).
"""
import argparse, json, pathlib, re, sys

# Язык → движок голоса. ky: другого у HeyGen нет. Для остальных eleven_v4 — тоже лучший из проверенных нами.
DVIZHOK_GOLOSA = {
    "ky": {"engine_type": "elevenlabs", "model": "eleven_v4"},
    "ru": {"engine_type": "elevenlabs", "model": "eleven_v4"},
    "kk": {"engine_type": "elevenlabs", "model": "eleven_v4"},
    "uz": {"engine_type": "elevenlabs", "model": "eleven_v4"},
    "en": {"engine_type": "elevenlabs", "model": "eleven_v4"},
}
DVIZHOK_AVATARA = {"iii": "avatar_iii", "iv": "avatar_iv", "v": "avatar_v", "6": "heygen-avatar-6-turbo"}
FORMAT = {"vertical": "9:16", "horizontal": "16:9"}
# Ориентир, кредитов за минуту (замеры и справка HeyGen, октябрь–ноябрь 2026). Точная цена — в HeyGen перед генерацией.
KREDITY_MIN = {"iii": 4, "iv": 31, "v": 48, "6": None}
# Нормальный темп речи в Reels, слов в секунду (кыргызские слова длиннее русских).
NORMA = {"ky": 2.2, "ru": 2.6}


def parametry(a):
    if a.lang not in DVIZHOK_GOLOSA:
        sys.exit(f"Язык {a.lang}: движок не проверен. Посмотри get_video_voice_capabilities и допиши DVIZHOK_GOLOSA.")
    if not 0.5 <= a.skorost <= 1.5:
        sys.exit("Скорость HeyGen — от 0.5 до 1.5.")
    p = {
        "avatarId": a.avatar,
        "voiceId": a.voice,
        "script": pathlib.Path(a.tekst).read_text(encoding="utf-8").strip() if a.tekst else "",
        "engine": {"type": DVIZHOK_AVATARA[a.dvizhok]},
        "aspectRatio": FORMAT[a.format],
        "resolution": "1080p",
        "caption": {"file_format": "srt"},
        "voiceSettings": {
            "speed": a.skorost,
            "engine_settings": dict(DVIZHOK_GOLOSA[a.lang]),
            # locale не задаём: «оригинальный акцент» голоса. Задать en-US и т.п. — и кыргызский поплывёт.
        },
    }
    zametki = [
        "engine_settings обязателен: без него HeyGen выберет движок сам — акцент.",
        "caption без style: субтитры отдельным файлом, в видео не вшиваются (монтаж ставит свои).",
        "resolution 1080p явно: без него Avatar III/IV/V отдают 720p.",
        f"Движок аватара {a.dvizhok.upper()} явно: по умолчанию HeyGen берёт Avatar 6 Turbo, его цену и вид мы ещё не проверяли.",
        "Ссылки get_video живут ~7 дней: mp4 и srt скачать сразу.",
        "Скорость в настройках HeyGen применяется не всегда: после рендера — heygen.py temp ФАЙЛ.srt.",
    ]
    k = KREDITY_MIN[a.dvizhok]
    if k:
        zametki.append(f"Ориентир цены: около {k} кр. за минуту ролика. Перед первым роликом сверить в HeyGen.")
    out = {"create_video_from_avatar": p, "zametki": zametki}
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if a.papka:
        f = pathlib.Path(a.papka) / "heygen.json"
        f.write_text(txt + "\n", encoding="utf-8")
        print(f"записал {f}", file=sys.stderr)
    print(txt)


def temp(a):
    t = pathlib.Path(a.srt).read_text(encoding="utf-8", errors="ignore")
    vremya = re.findall(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", t)
    if not vremya:
        sys.exit("В файле нет таймингов SRT.")
    sek = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    nachalo, konec = sek(*vremya[0][:4]), sek(*vremya[-1][4:])
    stroki = [s for s in t.splitlines() if s.strip() and not s.strip().isdigit() and "-->" not in s]
    slov = sum(len(re.findall(r"\w+", s)) for s in stroki)
    dlit = max(konec - nachalo, 0.1)
    v = slov / dlit
    norma = NORMA.get(a.lang, 2.6)
    print(f"{slov} слов за {dlit:.1f} с → {v:.2f} слова/с (норма для {a.lang}: от {norma})")
    if v >= norma:
        print("Темп нормальный, на монтаже не ускорять.")
    else:
        k = min(round(norma / v, 2), 1.25)
        print(f"Медленно. Ускорить на монтаже ×{k} (больше ×1.25 звучит неестественно), потом послушать:")
        print(f'  ffmpeg -i avatar.mp4 -filter_complex "[0:v]setpts=PTS/{k}[v];[0:a]atempo={k}[a]" -map "[v]" -map "[a]" avatar-x{k}.mp4')
        print(f"Тайминги слов после ускорения делить на {k}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parametry")
    p.add_argument("--avatar", required=True); p.add_argument("--voice", required=True)
    p.add_argument("--lang", default="ky"); p.add_argument("--format", choices=FORMAT, default="vertical")
    p.add_argument("--dvizhok", choices=DVIZHOK_AVATARA, default="iii"); p.add_argument("--skorost", type=float, default=1.2)
    p.add_argument("--papka"); p.add_argument("--tekst")
    t = sub.add_parser("temp")
    t.add_argument("srt"); t.add_argument("--lang", default="ky")
    a = ap.parse_args()
    parametry(a) if a.cmd == "parametry" else temp(a)


if __name__ == "__main__":
    main()
