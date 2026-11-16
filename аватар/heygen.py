"""Аватар HeyGen: точные настройки вызова и проверка темпа. Mac и Windows, только стандартная библиотека.

Коннектор HeyGen вызывает Claude, а настройки берёт отсюда. Руками их не собирай.

Схема (с 12.11.2026): сначала голос целиком, потом Avatar V только на куски, где видно лицо (≤30% ролика), остальное — Б-роллы.
Avatar III и IV в кадр не идут: картинка у них неживая. III нужен только как дешёвый способ получить голос.

  py heygen.py test  --avatar LOOK --voice VOICE [--lang ky] [--format vertical|horizontal] [--papka ПАПКА]
        → проба 5–10 с целиком на Avatar V: человек слушает голос и смотрит, живой ли аватар. Один раз, до первого ролика.
  py heygen.py golos --avatar LOOK --voice VOICE [--lang ky] [--format …] [--papka ПАПКА]
        → голос всего сценария. Рендер на Avatar III, но **из видео берём только звук**, картинку выкидываем.
          Для ky другого пути в HeyGen нет: create_speech кыргызский не знает (только HeyGen Voice, ky нет в списке).
  py heygen.py lico  --avatar LOOK --audio ASSET_ID [--format …]
        → кусок с лицом на Avatar V по готовому звуку (mp3-кусок из segs.py): голос не пересчитывается, губы совпадают.
  py heygen.py temp ФАЙЛ.srt [--lang ky]
        → слов в секунду по субтитрам и вердикт: темп нормальный или ускорить на монтаже.

Без --tekst поле script пустое: Claude вставляет утверждённый текст дословно. С --papka JSON пишется ещё и в ПАПКА/heygen-<режим>.json.

Проверено 16.11.2026 по get_video_voice_capabilities: для ky у HeyGen только движок elevenlabs, модели eleven_v3/eleven_v4, без locale.
Без engine_settings HeyGen выбирает движок клона сам — у учеников выходил акцент. eleven_v4 живее v3 (наша проверка 21.10.2026).
"""
import argparse, json, pathlib, re, sys

DVIZHOK_GOLOSA = {l: {"engine_type": "elevenlabs", "model": "eleven_v4"} for l in ("ky", "ru", "kk", "uz", "en")}
FORMAT = {"vertical": "9:16", "horizontal": "16:9"}
DVIZHENIE = "calm, natural, small occasional hand gestures, looks into the camera"
NORMA = {"ky": 2.2, "ru": 2.6}  # нормальный темп в Reels, слов в секунду


def golos_nastroiki(a):
    if a.lang not in DVIZHOK_GOLOSA:
        sys.exit(f"Язык {a.lang}: движок не проверен. Посмотри get_video_voice_capabilities и допиши DVIZHOK_GOLOSA.")
    # locale не задаём: «оригинальный акцент» голоса. Любой locale ломает кыргызский.
    return {"speed": a.skorost, "engine_settings": dict(DVIZHOK_GOLOSA[a.lang])}


def tekst(a):
    return pathlib.Path(a.tekst).read_text(encoding="utf-8").strip() if getattr(a, "tekst", None) else ""


def vyvod(a, rezhim, p, zametki):
    txt = json.dumps({"create_video_from_avatar": p, "zametki": zametki}, ensure_ascii=False, indent=2)
    if getattr(a, "papka", None):
        f = pathlib.Path(a.papka) / f"heygen-{rezhim}.json"
        f.write_text(txt + "\n", encoding="utf-8")
        print(f"записал {f}", file=sys.stderr)
    print(txt)


def test(a):
    p = {"avatarId": a.avatar, "voiceId": a.voice, "script": tekst(a), "engine": {"type": "avatar_v"},
         "motionPrompt": DVIZHENIE, "aspectRatio": FORMAT[a.format], "resolution": "1080p",
         "caption": {"file_format": "srt"}, "voiceSettings": golos_nastroiki(a)}
    vyvod(a, "test", p, [
        "Текст пробы — 1–2 фразы на 5–10 с, язык человека. Avatar V ≈1 кр./с: проба стоит около 7–10 кр.",
        "Человек слушает голос (похож, без акцента, темп) и смотрит лицо (живое, губы попадают). Вердикт — в local.md.",
        "Проба целиком на V только здесь. В роликах V идёт кусками на лицо: режимы golos → lico.",
    ])


def golos(a):
    p = {"avatarId": a.avatar, "voiceId": a.voice, "script": tekst(a), "engine": {"type": "avatar_iii"},
         "aspectRatio": FORMAT[a.format], "resolution": "720p", "caption": {"file_format": "srt"},
         "voiceSettings": golos_nastroiki(a)}
    vyvod(a, "golos", p, [
        "Это проход ТОЛЬКО ЗА ГОЛОСОМ. Картинку Avatar III в ролик не ставить: она неживая.",
        "Из mp4 достать звук: ffmpeg -i golos.mp4 -vn -ac 1 -ar 44100 -b:a 192k golos.mp3 (HeyGen берёт mp3, m4a — нет).",
        "srt проверить темп: heygen.py temp. Слова для монтажа и нарезки — words.json из srt или words.py.",
        "Дальше: план кадров → куски с лицом (≤30% ролика) → montazh segs.py режет mp3 → режим lico на каждый кусок.",
        "720p достаточно: картинка не нужна. Ссылки get_video живут ~7 дней — скачать сразу.",
    ])


def lico(a):
    p = {"avatarId": a.avatar, "audioAssetId": a.audio, "engine": {"type": "avatar_v"}, "motionPrompt": DVIZHENIE,
         "aspectRatio": FORMAT[a.format], "resolution": "1080p"}
    vyvod(a, "lico", p, [
        "audioAssetId: mp3-кусок из segs.py → create_asset_upload → PUT → complete_asset_upload. Голос и скорость задаёт сам звук.",
        "Длина куска = длина звука, губы совпадают. Готовые куски — в ПАПКА/v/N.mp4, сборка поверх голоса — montazh compose.py.",
        "Avatar V ≈1 кр./с куска: до генерации segs.py считает долю лица и кредиты, больше 30% — резать план.",
    ])


def temp(a):
    t = pathlib.Path(a.srt).read_text(encoding="utf-8", errors="ignore")
    vr = re.findall(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", t)
    if not vr:
        sys.exit("В файле нет таймингов SRT.")
    sek = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    dlit = max(sek(*vr[-1][4:]) - sek(*vr[0][:4]), 0.1)
    slov = sum(len(re.findall(r"\w+", s)) for s in t.splitlines() if s.strip() and not s.strip().isdigit() and "-->" not in s)
    v, norma = slov / dlit, NORMA.get(a.lang, 2.6)
    print(f"{slov} слов за {dlit:.1f} с → {v:.2f} слова/с (норма для {a.lang}: от {norma})")
    if v >= norma:
        print("Темп нормальный, не ускорять.")
    else:
        k = min(round(norma / v, 2), 1.25)
        print(f"Медленно. Ускорить голос ×{k} (больше ×1.25 звучит неестественно) ДО нарезки на куски, потом послушать:")
        print(f"  ffmpeg -i golos.mp3 -af atempo={k} golos-x{k}.mp3   и тайминги слов делить на {k}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for imya in ("test", "golos"):
        p = sub.add_parser(imya)
        p.add_argument("--avatar", required=True); p.add_argument("--voice", required=True)
        p.add_argument("--lang", default="ky"); p.add_argument("--skorost", type=float, default=1.2)
        p.add_argument("--format", choices=FORMAT, default="vertical"); p.add_argument("--papka"); p.add_argument("--tekst")
    p = sub.add_parser("lico")
    p.add_argument("--avatar", required=True); p.add_argument("--audio", required=True)
    p.add_argument("--format", choices=FORMAT, default="vertical"); p.add_argument("--papka")
    t = sub.add_parser("temp"); t.add_argument("srt"); t.add_argument("--lang", default="ky")
    a = ap.parse_args()
    if not 0.5 <= getattr(a, "skorost", 1.0) <= 1.5:
        sys.exit("Скорость HeyGen — от 0.5 до 1.5.")
    {"test": test, "golos": golos, "lico": lico, "temp": temp}[a.cmd](a)


if __name__ == "__main__":
    main()
