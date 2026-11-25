"""Образы (луки) аватара в HeyGen: проверка исходных фото, загрузка, готовые шаблоны образов. Mac и Windows, только стандартная библиотека + ffmpeg.

Почему так (урок 8 Бобби, 25.11.2026, проба Kie против HeyGen):
  - образ в HeyGen (create_prompt_avatar в группу своего аватара) стоит 1 кредит HeyGen и сразу лежит в аватаре, готов к ролику;
    Kie Nano Banana Pro 4K — 24 кредита Kie (~$0,12) за картинку, и её ещё надо загружать в HeyGen. По умолчанию — HeyGen;
  - HeyGen отдаёт ~1536×2752: для вертикали 1080×1920 запаса хватает, на видео аватара разницы с 4K не видно;
  - сходство держат ИСХОДНЫЕ ФОТО (референсы), а не текст. Лицо в промпте не описывать: глаза, нос, очки в тексте —
    и модель рисует человека заново («индус», «старый»). Промпт говорит только, что меняется: одежда, комната, свет;
  - плохое исходное фото (телефон в темноте, мыло, рот открыт, лицо мелкое) = непохожие образы. Поэтому сначала `proverka`;
  - свет из окна сбоку делает лицо тёмным, лофт выходит мыльнее — в шаблонах везде мягкий свет спереди и комната в фокусе;
  - править всегда от исходного фото, не от сгенерированного: каждая правка поверх генерации уводит лицо.
  - референсы — только настоящие фото: лица из сгенерированных образов (даже удачных) дают «не похож» (проба 25.11).

  py obrazy.py proverka ФОТО [ФОТО ...]        → разрешение и резкость каждого фото + что проверить глазами. Ничего не тратит.
  py obrazy.py shablony                       → список готовых образов.
  py obrazy.py zagruzka ФОТО [ФОТО ...]        → JSON для create_asset_upload_batch (фото → HeyGen, бесплатно).
  py obrazy.py put ОТВЕТ.json ФОТО [ФОТО ...]  → PUT фото по upload_url, потом complete_asset_batch → get_asset_batch.
  py obrazy.py zapros --aktivy ОТВЕТ.json [--shablon 1,2,3|vse|avatarka] [--svoi "одежда и место своими словами"]
                     [--gruppa ID] [--format 9:16|16:9|1:1] [--imya ИМЯ]
        → готовые вызовы create_prompt_avatar (по одному на образ) + сколько кредитов. Группа — из завод/аватар.json (heygen.py nastroit).
"""
import argparse, json, pathlib, re, subprocess, sys, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from heygen import zagruzit, obkhod  # noqa: E402

TIPY = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

# Общее для всех образов: лицо не описываем, только «оставь как на фото».
NACHALO = ("The same person as in the reference photos: keep the face, hair, skin tone, age and body exactly as they are, "
           "a real photograph of this person, not a redrawn face. Straight-on front view at eye level, looking into the camera, "
           "calm confident expression, mouth closed.")
KONETS = ("Soft frontal key light evenly lighting the face, no dark shadows on the face. The room in focus and clearly readable. "
          "Real skin texture with pores, no retouching, no plastic skin. Photorealistic photo on a professional camera, ultra detailed.")

# Шаблоны: проверены на пробе 25.11 (1 — лучший у Бобби). Одежда — дорогие спокойные оттенки, подходит и мужчине, и женщине.
SHABLONY = {
    "1": ("Подкаст-студия вечером, чёрная рубашка", "9:16",
          "Sitting at a dark walnut desk. Wearing a black linen shirt, top button open, sleeves rolled to the forearms, a steel watch. "
          "Evening home podcast studio: walnut shelves with a few books and ceramics, a warm table lamp, a soft LED strip, "
          "a podcast microphone on a boom arm at the side, not covering the face."),
    "2": ("Комната блогера днём, графитовая оверсайз-футболка", "9:16",
          "Sitting at a light oak desk, hands relaxed on the desk. Wearing a premium heavyweight oversized t-shirt in deep graphite gray. "
          "Modern minimal creator room: warm microcement wall, light-oak slats, a paper floor lamp, an olive tree, "
          "a podcast microphone on a boom arm at the side."),
    "3": ("Лофт, тёмно-синяя рубашка поверх белой футболки", "9:16",
          "Sitting at a desk. Wearing a dark navy wool overshirt open over a plain white heavyweight t-shirt. "
          "Loft office of a content creator: exposed brick wall, black steel windows, a monitor with a soft glow, plants, "
          "a podcast microphone on a boom arm at the side."),
    "4": ("Светлая квартира утром, кремовый свитшот", "9:16",
          "Sitting at a light wooden table. Wearing a heavyweight oversized sweatshirt in warm cream-oatmeal color. "
          "Bright Scandinavian apartment in the morning: white walls, linen curtains, a vase with dry branches, a laptop on the table, "
          "a podcast microphone on a small stand. The window is behind the camera, not at the side."),
    "5": ("Тёмная студия, чёрный костюм", "9:16",
          "Sitting at a black desk, shoulders square, composed. Wearing a perfectly tailored all-black suit with a black shirt, no tie, "
          "a minimal black-dial watch. Dark moody studio: charcoal acoustic panels, one warm practical lamp behind, "
          "a matte black podcast microphone on a boom arm at the side, a faint edge light separating the suit from the background."),
    "6": ("Светлая студия, белая рубашка", "9:16",
          "Sitting at a concrete-and-wood desk, leaning slightly forward on the forearms. Wearing a crisp white shirt, relaxed fit, "
          "top two buttons open, sleeves rolled up. Bright studio with plants, a leather chair and soft daylight from behind the camera, "
          "a podcast microphone on a boom arm at the side."),
    "7": ("Горизонтальный для YouTube и уроков, графитовая футболка", "16:9",
          "Seated slightly left of center at a dark wooden desk, framed from the waist up, hands resting on the desk. "
          "Wearing a heavyweight dark charcoal oversized t-shirt. Wide cozy podcast studio fills the right side of the frame: "
          "acoustic slat wall, a bookshelf with warm lamps, a tall plant, a podcast microphone on a boom arm, an open laptop."),
    "avatarka": ("Аватарка для соцсетей", "1:1",
                 "Square social media profile photo, tight head-and-shoulders crop, face centered and large. Slight natural smile. "
                 "Wearing a crisp white shirt with an open collar. Smooth seamless dark charcoal backdrop, no objects, "
                 "the face and shirt clearly stand out from the background. Do not age the person, keep the same age as in the photos."),
}


def razmer(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    try:
        w, h = [int(x) for x in r.stdout.strip().split(",")[:2]]
        return w, h
    except ValueError:
        return None


def rezkost(f):
    """Насколько фото теряет детали от лёгкого размытия (PSNR, дБ). Резкое ≈ 39–40, мыло/растянутое ≥ 44.
    Откалибровано 25.11.2026 на студийных 4K-фото Бобби и их размытых копиях. Число — подсказка, глазами смотреть всё равно."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-filter_complex",
                        "[0:v]scale=1080:-2,format=gray,split[a][b];[b]gblur=sigma=1.2[c];[a][c]psnr", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"average:([0-9.]+)", r.stderr)
    return float(m.group(1)) if m else None


def proverka(a):
    plohie = 0
    for f in map(pathlib.Path, a.foto):
        if not f.exists():
            print(f"✗ {f}: файла нет"); plohie += 1; continue
        wh = razmer(f)
        if not wh:
            sovet = " На Mac: sips -s format jpeg фото.heic --out фото.jpg" if f.suffix.lower() in (".heic", ".heif") else ""
            print(f"✗ {f.name}: не открылось. Сохрани как JPG или PNG.{sovet}"); plohie += 1; continue
        w, h = wh
        k = min(w, h)
        if k >= 2000:
            ocenka = "✓ разрешение отличное"
        elif k >= 1080:
            ocenka = "! разрешение среднее: для крупного плана годится, общий лучше снять в полном размере основной камерой"
        else:
            ocenka = "✗ разрешение мало: переснять (скриншот, фото из WhatsApp/Telegram и сжатые фото не годятся)"; plohie += 1
        s = rezkost(f)
        if s is None:
            rz = "резкость не измерил (старый ffmpeg) — проверь глазами"
        elif s < 41.5:
            rz = f"✓ резкое ({s:.1f})"
        elif s < 44:
            rz = f"! мягкое ({s:.1f}): протри камеру, больше света, телефон неподвижно"
        else:
            rz = f"✗ мыло ({s:.1f}): переснять"; plohie += 1
        print(f"{f.name}: {w}×{h} — {ocenka}; {rz}")
    print("\nГлазами (Claude смотрит каждое фото, Read): лицо открыто и в фокусе; рот закрыт; взгляд в камеру, анфас;"
          "\n  свет спереди, лицо светлое, без резких теней; без очков (очки модель рисует по-своему и меняет глаза);"
          "\n  нужно минимум 2 фото: КРУПНЫЙ (лицо и плечи, лицо ≥ трети кадра) и ОБЩИЙ (по пояс). Петличку и мелочи ИИ уберёт.")
    print("\nИТОГ: " + ("фото годятся — можно делать образы." if not plohie else
                        f"{plohie} фото не годятся. Переснять: дневной свет из окна ПЕРЕД лицом, основная камера телефона, "
                        "без зума и фильтров, телефон на уровне глаз, рот закрыт, спокойный фон. Плохое фото = непохожие образы."))


def zagruzka(a):
    files = []
    for f in map(pathlib.Path, a.foto):
        t = TIPY.get(f.suffix.lower())
        if not t:
            sys.exit(f"{f.name}: нужен JPG или PNG (сначала proverka).")
        files.append({"filename": f.name, "content_type": t, "size_bytes": f.stat().st_size})
    print(json.dumps({"create_asset_upload_batch": {"title": "фото для образов", "files": files}, "zametki": [
        "Ответ коннектора целиком сохрани в obrazy/zagruzka.json, потом: obrazy.py put obrazy/zagruzka.json ФОТО … (те же фото, тот же порядок).",
        "Загрузка бесплатная."]}, ensure_ascii=False, indent=2))


def put(a):
    d = json.loads(pathlib.Path(a.otvet).read_text(encoding="utf-8"))
    foto = [pathlib.Path(f) for f in a.foto]
    zapisi = [x for x in obkhod(d) if x.get("upload_url")]
    if len(zapisi) != len(foto):
        sys.exit(f"В ответе {len(zapisi)} upload_url, а фото {len(foto)}. Нужен ответ create_asset_upload_batch целиком и те же фото.")
    for x, f in zip(zapisi, foto):
        zag = x.get("upload_headers") or x.get("headers") or {}
        if isinstance(zag, list):
            zag = {h.get("name") or h.get("key"): h.get("value") for h in zag}
        zag = {k: str(v) for k, v in zag.items()}
        if not any(k.lower() == "content-type" for k in zag):
            zag["Content-Type"] = TIPY[f.suffix.lower()]
        req = urllib.request.Request(x["upload_url"], data=f.read_bytes(), method="PUT", headers=zag)
        with urllib.request.urlopen(req, timeout=300) as r:
            if r.status not in (200, 201, 204):
                sys.exit(f"{f.name}: загрузка вернула {r.status}")
        print(f"✓ {f.name} загружено")
    bid = next((x.get("batch_id") or x.get("batchId") for x in obkhod(d) if x.get("batch_id") or x.get("batchId")), "<batch_id>")
    print(f"Дальше: complete_asset_batch batchId={bid} → get_asset_batch, пока все completed → obrazy.py zapros --aktivy {a.otvet}")


def aktivy(f):
    d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
    # ответ create_asset_upload_batch (asset_id) или get_asset_batch (там id лежит в video_id — проверено 25.11.2026)
    ids = [x.get("asset_id") or x.get("video_id") for x in obkhod(d) if x.get("upload_url") or x.get("asset_id") or "item_index" in x]
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        sys.exit("В ответе не нашёл asset_id. Сохрани ответ create_asset_upload_batch целиком, без пересказа.")
    return ids[:3]  # create_prompt_avatar берёт до 3 референсов: крупный первым


def zapros(a):
    gruppa = a.gruppa or zagruzit().get("gruppa")
    if not gruppa:
        sys.exit("Нет группы аватара: сначала heygen.py nastroit (list_avatar_groups) или --gruppa ID. "
                 "Аватара ещё нет — сначала урок «Аватар HeyGen»: Digital Twin из видео.")
    refs = [{"type": "asset_id", "asset_id": i} for i in aktivy(a.aktivy)]
    if a.svoi:
        spisok = [("Свой образ", a.format or "9:16", a.svoi)]
    else:
        klyuchi = list(SHABLONY) if a.shablon == "vse" else [k.strip() for k in a.shablon.split(",") if k.strip()]
        neizv = [k for k in klyuchi if k not in SHABLONY]
        if neizv:
            sys.exit(f"Нет шаблонов {neizv}. Есть: {', '.join(SHABLONY)} (obrazy.py shablony).")
        spisok = [(SHABLONY[k][0], a.format or SHABLONY[k][1], SHABLONY[k][2]) for k in klyuchi]
    vyzovy = []
    for imya, fmt, scena in spisok:
        prompt = f"{NACHALO} {scena} {KONETS}"
        if len(prompt) > 1000:
            sys.exit(f"«{imya}»: промпт {len(prompt)} знаков, HeyGen берёт до 1000. Сократи описание (--svoi).")
        vyzovy.append({"create_prompt_avatar": {"name": f"{a.imya} · {imya}", "avatarGroupId": gruppa, "aspectRatio": fmt,
                                                "prompt": prompt, "referenceImages": refs}})
    print(json.dumps({"vyzovy": vyzovy, "kredity": len(vyzovy), "zametki": [
        f"Цена: {len(vyzovy)} кр. HeyGen (1 за образ). Назови человеку и жди «да», если в local.md не сказано иначе.",
        "Вызывай по одному, потом show_avatar_looks с id образов — человек видит их в карточке.",
        "Сверь каждый образ с исходным фото: глаза, нос, борода/брови, возраст. Не похож — тот же вызов ещё раз (новая попытка), "
        "текст про лицо НЕ добавляй. Не похож дважды — фото слабое: proverka и переснять.",
        "Понравившийся образ — его look_id в завод/аватар.json: heygen.py nastroit … --look ID."]}, ensure_ascii=False, indent=2))


def shablony(_):
    for k, (imya, fmt, _s) in SHABLONY.items():
        print(f"{k:>8}  {fmt:5}  {imya}")
    print("\nСвой образ: zapros --svoi \"одежда и место по-английски\" (лицо не описывать).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("proverka"); p.add_argument("foto", nargs="+")
    sub.add_parser("shablony")
    p = sub.add_parser("zagruzka"); p.add_argument("foto", nargs="+")
    p = sub.add_parser("put"); p.add_argument("otvet"); p.add_argument("foto", nargs="+")
    p = sub.add_parser("zapros"); p.add_argument("--aktivy", required=True); p.add_argument("--shablon", default="1,2,3")
    p.add_argument("--svoi"); p.add_argument("--gruppa"); p.add_argument("--format", choices=["9:16", "16:9", "1:1", "4:5"])
    p.add_argument("--imya", default="Я")
    a = ap.parse_args()
    {"proverka": proverka, "shablony": shablony, "zagruzka": zagruzka, "put": put, "zapros": zapros}[a.cmd](a)


if __name__ == "__main__":
    main()
