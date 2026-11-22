"""Аватар HeyGen по гибридной схеме: точные настройки вызовов, план лица, загрузка кусков. Mac и Windows, только стандартная библиотека.

Коннектор HeyGen вызывает Claude, а настройки, голос и план берёт отсюда. Руками их не собирай.

Схема (Бобби, 12.11 и 22.11.2026):
  1) голос всего ролика — в самом HeyGen, голос аватара (клон) на ElevenLabs v4, проход на дешёвом Avatar III, из видео берём только звук;
  2) лёгкое ускорение голоса (temp → uskorit);
  3) лицо 20–30% ролика: начало (или с 3-й секунды), 1–2 раза в середине, призыв в конце (plan);
  4) куски звука → HeyGen (zagruzka → put) → лицо на Avatar 6 Turbo по готовому звуку (lico): губы совпадают, голос тот же;
  5) монтаж: голос сплошной, лицо на своих местах, между ними Б-роллы — кажется, что аватар говорит всё время.

  py heygen.py nastroit --gruppy groups.json [--golosa voices.json] [--gruppa ИМЯ|ID] [--look ID] [--lang ky] [--model 6turbo]
        → один раз: голос берётся из настройки аватара в HeyGen (default_voice_id группы), а не из list_voices. Пишет завод/аватар.json.
  py heygen.py test  [--tekst Ф] [--papka П]   → проба 5–10 с целиком на модели лица: голос и лицо. Один раз, до первого ролика.
  py heygen.py golos [--tekst Ф] [--papka П]   → голос всего сценария (Avatar III, только звук).
  py heygen.py temp  ФАЙЛ.srt                  → темп и коэффициент лёгкого ускорения.
  py heygen.py slova ФАЙЛ.srt [--k K]          → words.json из субтитров HeyGen (тайминги делятся на K после ускорения).
  py heygen.py uskorit golos.mp3 --k K         → golos-xK.mp3 (ffmpeg atempo).
  py heygen.py plan --tekst Ф [--words words.json] [--dolya 25] [--start 0|3] [--papka П]
        → какие куски идут на лицо, доля, кредиты, команда segs.py. Без --words — оценка по тексту, без генерации.
  py heygen.py zagruzka ПАПКА_КУСКОВ           → JSON для create_asset_upload_batch (точные size_bytes и тип mp3).
  py heygen.py put ОТВЕТ.json --papka ПАПКА_КУСКОВ → PUT каждого mp3 по upload_url с заголовками HeyGen, потом complete_asset_batch.
  py heygen.py lico --aktivy ОТВЕТ.json | --audio ASSET_ID [--model 6turbo|6pro|v] → вызовы лица по готовому звуку.

Проверено 22.11.2026 по коннектору: get_video_voice_capabilities — для ky только elevenlabs (eleven_v3/v4), без locale;
create_video_from_avatar по умолчанию берёт Avatar 6 Turbo; list_voices показывает только голоса HeyGen Voice (кыргызский не знают),
а рабочий клон под ElevenLabs стоит в аватаре: list_avatar_groups → default_voice_id.
"""
import argparse, json, math, pathlib, re, subprocess, sys, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
try:
    from zavod_obshchee import zavod, programma
except Exception:  # запуск отдельно от завода
    zavod = lambda: pathlib.Path.home() / "Projects" / "завод"
    programma = lambda n: n

DVIZHOK_GOLOSA = {l: {"engine_type": "elevenlabs", "model": "eleven_v4"} for l in ("ky", "ru", "kk", "uz", "en")}
FORMAT = {"vertical": "9:16", "horizontal": "16:9"}
DVIZHENIE = "calm, natural, small occasional hand gestures, looks into the camera"
NORMA = {"ky": 2.2, "ru": 2.6}  # нормальный темп в Reels, слов в секунду
SKOROST = 1.2                   # скорость голоса в HeyGen (применяется не всегда — потом temp)
# модель лица: engine для create_video_from_avatar и кредиты за минуту (help.heygen.com, проверено 22.11.2026)
MODELI = {
    "6turbo": ({"type": "heygen-avatar-6-turbo"}, 20, "Avatar 6 Turbo — по умолчанию: новее и живее V, в 2,4 раза дешевле, есть на Creator"),
    "6pro": ({"type": "heygen-avatar-6"}, 40, "Avatar 6 Pro — качество выше, кредитов вдвое больше; только тариф Pro и выше"),
    "v": ({"type": "avatar_v"}, 60, "Avatar V — прошлое поколение; 48 кр./мин по справке, наш замер ≈1 кр./с"),
}
GOLOS_KR_MIN = 4                # Avatar III, видео-образ: кредитов за минуту прохода за голосом
NASTROIKI = lambda: zavod() / "аватар.json"
clean = lambda s: re.sub(r"[^a-zа-яёңөүәіұқғһ0-9]", "", s.lower())  # как в montazh segs.py


# ---------- настройки аватара ----------
def zagruzit():
    f = NASTROIKI()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def items(f):
    d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
    return d.get("items", d.get("data", d)) if isinstance(d, dict) else d


def nastroit(a):
    gruppy = [g for g in items(a.gruppy) if isinstance(g, dict)]
    if a.gruppa:
        gruppy = [g for g in gruppy if a.gruppa in (g.get("id"), g.get("name"))]
    if len(gruppy) != 1:
        imena = ", ".join(f"{g.get('name')} ({g.get('id')})" for g in gruppy) or "нет своих аватаров"
        sys.exit(f"Выбери одного аватара флагом --gruppa: {imena}. Нет аватара — сделать в HeyGen: Avatars → Create → Digital Twin.")
    g = gruppy[0]
    golos = g.get("default_voice_id")
    if not golos:
        sys.exit(f"У аватара «{g.get('name')}» не выбран голос. Человек делает сам в HeyGen (сайт): Avatars → «{g.get('name')}» → "
                 "Voice → свой клон голоса. Потом снова list_avatar_groups → nastroit.")
    chuzhie = [v.get("voice_id") for v in items(a.golosa)] if a.golosa else []
    if golos in chuzhie and a.lang == "ky":
        sys.exit("Голос аватара сделан на HeyGen Voice — кыргызский он не знает, ElevenLabs v4 его не возьмёт. Человек в HeyGen: "
                 "Voices → Clone voice (запись 20+ мин) → в аватаре Voice → этот клон. Потом nastroit заново.")
    s = {"gruppa": g.get("id"), "imya": g.get("name"), "look": a.look or "", "voice": golos, "lang": a.lang, "model": a.model,
         "heygen_voice": chuzhie}
    NASTROIKI().parent.mkdir(parents=True, exist_ok=True)
    NASTROIKI().write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"записал {NASTROIKI()}: аватар «{g.get('name')}», голос из аватара {golos}, язык {a.lang}, лицо — {MODELI[a.model][2]}")
    if not a.look:
        print("Лук не выбран: list_avatar_looks группы → человек выбирает → nastroit ещё раз с --look.")


def vzyat(a, pole):
    v = getattr(a, pole, None) or zagruzit().get(pole)
    if not v:
        sys.exit(f"Нет {pole}: сначала `heygen.py nastroit` (голос и лук берутся из аватара в HeyGen).")
    if pole == "voice" and v in zagruzit().get("heygen_voice", []) and yazyk(a) == "ky":
        sys.exit("Это голос HeyGen Voice из list_voices: кыргызский он не знает. Голос — только из аватара (nastroit).")
    return v


def yazyk(a):
    return getattr(a, "lang", None) or zagruzit().get("lang") or "ky"


def golos_nastroiki(a):
    l = yazyk(a)
    if l not in DVIZHOK_GOLOSA:
        sys.exit(f"Язык {l}: движок не проверен. Посмотри get_video_voice_capabilities и допиши DVIZHOK_GOLOSA.")
    # locale не задаём: «оригинальный акцент» голоса. Любой locale ломает кыргызский.
    return {"speed": a.skorost, "engine_settings": dict(DVIZHOK_GOLOSA[l])}


def model(a):
    return getattr(a, "model", None) or zagruzit().get("model") or "6turbo"


def tekst(a):
    return pathlib.Path(a.tekst).read_text(encoding="utf-8").strip() if getattr(a, "tekst", None) else ""


def vyvod(a, rezhim, p, zametki):
    txt = json.dumps({"create_video_from_avatar": p, "zametki": zametki}, ensure_ascii=False, indent=2)
    if getattr(a, "papka", None):
        f = pathlib.Path(a.papka) / f"heygen-{rezhim}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt + "\n", encoding="utf-8")
        print(f"записал {f}", file=sys.stderr)
    print(txt)


def litso(a, p):
    eng, _, _ = MODELI[model(a)]
    p.update({"engine": dict(eng), "motionPrompt": DVIZHENIE, "resolution": "1080p"})
    if model(a) != "v":
        p["motionExpressiveness"] = "less"
    return p


# ---------- вызовы ----------
def test(a):
    p = litso(a, {"avatarId": vzyat(a, "look"), "voiceId": vzyat(a, "voice"), "script": tekst(a),
                  "aspectRatio": FORMAT[a.format], "caption": {"file_format": "srt"}, "voiceSettings": golos_nastroiki(a)})
    kr = MODELI[model(a)][1]
    vyvod(a, "test", p, [
        f"Текст пробы — 1–2 фразы на 5–10 с, язык человека. {MODELI[model(a)][2]}: ≈{kr} кр./мин, проба ≈{math.ceil(kr / 6)} кр.",
        "Человек слушает голос (похож, без акцента, темп) и смотрит лицо (живое, губы попадают). Вердикт — в local.md.",
        "Проба целиком только здесь. В роликах лицо идёт кусками: golos → plan → zagruzka → put → lico.",
    ])


def golos(a):
    p = {"avatarId": vzyat(a, "look"), "voiceId": vzyat(a, "voice"), "script": tekst(a), "engine": {"type": "avatar_iii"},
         "aspectRatio": FORMAT[a.format], "resolution": "720p", "caption": {"file_format": "srt"},
         "voiceSettings": golos_nastroiki(a)}
    vyvod(a, "golos", p, [
        f"Проход ТОЛЬКО ЗА ГОЛОСОМ: Avatar III ≈{GOLOS_KR_MIN} кр./мин. Картинку III в ролик не ставить: она неживая.",
        "engine avatar_iii задан явно: без него коннектор возьмёт Avatar 6 Turbo, это в 5 раз дороже.",
        "get_video → скачать mp4 и srt сразу (ссылки ~7 дней). Звук: ffmpeg -i golos.mp4 -vn -ac 1 -ar 44100 -b:a 192k golos.mp3",
        "Дальше: heygen.py temp golos.srt → uskorit → slova → plan --words → montazh segs.py → zagruzka → put → lico.",
    ])


def lico(a):
    if a.aktivy:
        aktivy = najti_aktivy(json.loads(pathlib.Path(a.aktivy).read_text(encoding="utf-8")))
    elif a.audio:
        aktivy = [("кусок", a.audio)]
    else:
        sys.exit("Нужно --aktivy ОТВЕТ.json (create_asset_upload_batch) или --audio ASSET_ID.")
    look = vzyat(a, "look")
    vyzovy = [{"kusok": f, "create_video_from_avatar": litso(a, {"avatarId": look, "audioAssetId": aid,
                                                              "aspectRatio": FORMAT[a.format]})} for f, aid in aktivy]
    txt = json.dumps({"vyzovy": vyzovy, "zametki": [
        "Каждый кусок — отдельный create_video_from_avatar ровно с этим JSON. voiceSettings не нужен: звук готовый.",
        "Длина куска = длина звука, губы совпадают. Готовое — в ПАПКА/v/N.mp4 (N — номер seg-N), сборка — montazh compose.py.",
        "Перед запуском назвать кредиты из heygen.py plan. Генерацию запускать после complete_asset_batch.",
    ]}, ensure_ascii=False, indent=2)
    if a.papka:
        (pathlib.Path(a.papka) / "heygen-lico.json").write_text(txt + "\n", encoding="utf-8")
    print(txt)


# ---------- темп, слова, ускорение ----------
def srt_cues(f):
    t = pathlib.Path(f).read_text(encoding="utf-8", errors="ignore")
    sek = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for blok in re.split(r"\n\s*\n", t.strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", blok)
        if m:
            txt = " ".join(s for s in blok.splitlines()[blok.splitlines().index(next(l for l in blok.splitlines() if "-->" in l)) + 1:])
            cues.append((sek(*m.groups()[:4]), sek(*m.groups()[4:]), txt))
    if not cues:
        sys.exit("В файле нет таймингов SRT.")
    return cues


def temp(a):
    cues = srt_cues(a.srt)
    dlit = max(cues[-1][1] - cues[0][0], 0.1)
    slov = sum(len(re.findall(r"\w+", c[2])) for c in cues)
    v, norma = slov / dlit, NORMA.get(yazyk(a), 2.6)
    k = min(max(round(norma * 1.05 / v, 2), 1.0), 1.25)  # цель — чуть живее нормы; больше ×1.25 звучит неестественно
    print(f"{slov} слов за {dlit:.1f} с → {v:.2f} слова/с (норма для {yazyk(a)}: от {norma})")
    if k <= 1.02:
        print("Темп нормальный, не ускорять: --k 1.0")
    else:
        print(f"Лёгкое ускорение ×{k} ДО нарезки, потом послушать: heygen.py uskorit golos.mp3 --k {k} и heygen.py slova ФАЙЛ.srt --k {k}")


def slova(a):
    out = []
    for s, e, txt in srt_cues(a.srt):
        w = txt.split()
        if not w:
            continue
        ves = [len(x) + 1 for x in w]
        t = s
        for x, vv in zip(w, ves):
            d = (e - s) * vv / sum(ves)
            out.append({"text": x, "start": round(t / a.k, 3), "end": round((t + d) / a.k, 3)})
            t += d
    f = pathlib.Path(a.out or pathlib.Path(a.srt).with_name("words.json"))
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"записал {f}: {len(out)} слов (тайминги внутри строки субтитров — по длине слов; точнее — montazh words.py)")


def uskorit(a):
    src = pathlib.Path(a.mp3)
    dst = src.with_name(f"{src.stem}-x{a.k}.mp3")
    if not 1.0 <= a.k <= 1.25:
        sys.exit("Ускорение — от 1.0 до 1.25.")
    subprocess.run([programma("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-af", f"atempo={a.k}", "-ac", "1", "-ar", "44100",
                    "-b:a", "192k", str(dst)], check=True)
    print(f"записал {dst}. Дальше этот файл — сплошной голос ролика; слова — heygen.py slova ФАЙЛ.srt --k {a.k}")


# ---------- план лица ----------
def slova_iz_teksta(t, lang):
    """Оценка таймингов по тексту (до генерации): темп нормы, слово по длине, пауза 0,3 с после точки."""
    w, t0, v = [], 0.0, NORMA.get(lang, 2.6) * 1.05
    sr = sum(len(x) + 1 for x in t.split()) / max(len(t.split()), 1)
    for x in t.split():
        d = (len(x) + 1) / sr / v
        w.append({"text": x, "start": round(t0, 3), "end": round(t0 + d, 3)})
        t0 += d + (0.3 if re.search(r"[.!?…]$", x) else 0)
    return w


def predlozheniya(w):
    out, nach = [], 0
    for i, x in enumerate(w):
        if re.search(r"[.!?…]\W*$", x["text"]) or i == len(w) - 1:
            out.append((nach, i))
            nach = i + 1
    return out


def spec(w, i, j):
    n = lambda k: sum(1 for x in w[:k + 1] if clean(x["text"]) == clean(w[k]["text"]))
    ref = lambda k: re.sub(r"[\s\"']", "", w[k]["text"]) + f"#{n(k)}"
    return f"{ref(i)}..{ref(j)}"


def kusok(w, i, j, dur, pad, maxs, s_kontsa=False):
    """Кусок по словам i..j, не длиннее maxs с (с запасом pad). s_kontsa — обрезать начало (для призыва), иначе конец."""
    t = lambda i, j: min(dur, (w[j + 1]["start"] if j + 1 < len(w) else dur) + pad) - max(0, w[i]["start"] - pad)
    i0, j0 = i, j
    while i < j and t(i, j) > maxs:
        if s_kontsa:
            i += 1
        else:
            j -= 1
    if (i, j) != (i0, j0):  # обрезали — ставим край на запятую/двоеточие, если она в последней трети куска
        if s_kontsa:
            z = [k for k in range(i - 1, j - 1) if k >= i0 and re.search(r"[,:;—–]$", w[k]["text"]) and k + 1 - i <= (j - i) / 3]
            i = z[-1] + 1 if z else i
        else:
            z = [k for k in range(i, j) if re.search(r"[,:;—–]$", w[k]["text"]) and k - i >= (j - i) * 2 / 3]
            j = z[-1] if z else j
    return i, j, t(i, j)


def plan(a):
    lang = yazyk(a)
    if a.words:
        w, otkuda = json.loads(pathlib.Path(a.words).read_text(encoding="utf-8")), "words.json (точно)"
    else:
        w, otkuda = slova_iz_teksta(tekst(a), lang), "оценка по тексту (до генерации)"
    if len(w) < 8:
        sys.exit("Слишком короткий текст для плана.")
    dur = w[-1]["end"] + 0.3
    pr = predlozheniya(w)
    byudzhet = dur * min(a.dolya, 30) / 100
    kuski = []

    # 1) начало: с 0 с или с первого слова после 3-й секунды
    # с 3-й секунды: первая фраза, что начинается не раньше ~2,5 с (первые секунды — Б-ролл-хук)
    i0 = 0 if a.start == 0 else next((i for i, _ in pr if w[i]["start"] >= a.start - 0.5), 0)
    j0 = next(j for i, j in pr if j >= i0)
    while w[j0]["end"] - w[i0]["start"] < 2.5 and any(i > j0 for i, _ in pr[:-1]):  # огрызок фразы — берём и следующую
        j0 = next(j for i, j in pr if i > j0)
    kuski.append(("начало (хук)",) + kusok(w, i0, j0, dur, a.pad, min(4.0, byudzhet * 0.45)))
    # 2) призыв в конце: последнее предложение, обрезаем начало
    il, jl = pr[-1]
    kuski.append(("призыв (конец)",) + kusok(w, max(il, kuski[0][2] + 1), jl, dur, a.pad, min(5.0, byudzhet * 0.55), s_kontsa=True))
    # 3) середина: 1–2 предложения около 40% и 65% ролика, пока влезают в бюджет
    for tochka in (0.4, 0.65):
        ost = byudzhet - sum(k[3] for k in kuski)
        if ost < 1.5:
            break
        kand = [(i, j) for i, j in pr if i > kuski[0][2] and j < kuski[1][1]
                and all(j < k[1] - 1 or i > k[2] + 1 for k in kuski)]
        if not kand:
            break
        i, j = min(kand, key=lambda p: abs(w[p[0]]["start"] - dur * tochka))
        k = kusok(w, i, j, dur, a.pad, min(3.5, ost))
        if k[2] >= 1.2:
            kuski.append((f"середина ~{int(tochka * 100)}%",) + k)
    kuski.sort(key=lambda k: k[1])
    # бюджет в коде: больше 30% — режем середину, потом укорачиваем
    while sum(k[3] for k in kuski) > dur * 0.30 and len(kuski) > 2:
        kuski.remove(max((k for k in kuski if k[0].startswith("середина")), key=lambda k: k[3]))
    lico_s = sum(k[3] for k in kuski)
    if lico_s > dur * 0.30:
        sys.exit(f"Лицо {lico_s:.1f} с из {dur:.1f} — больше 30%: ролик слишком короткий, оставь только начало или призыв.")

    m = model(a)
    eng, kr_min, opis = MODELI[m]
    kr_lico = sum(math.ceil(k[3] * kr_min / 60) for k in kuski)
    kr_golos = math.ceil(dur * GOLOS_KR_MIN / 60)
    look, voice = zagruzit().get("look") or "<лук>", zagruzit().get("voice") or "<голос из аватара>"
    print(f"Ролик ≈{dur:.1f} с · тайминги: {otkuda}")
    print(f"\n1) ГОЛОС — весь текст одним проходом в HeyGen (heygen.py golos):")
    print(f"   Avatar III (только звук) · голос {voice} · ElevenLabs eleven_v4 · язык {lang}, без locale · скорость {SKOROST} · ≈{kr_golos} кр.")
    print(f"   Потом лёгкое ускорение: heygen.py temp → uskorit (×1.0–1.25).")
    print(f"\n2) ЛИЦО — {opis}; лук {look}; голос не пересчитывается (audioAssetId):")
    for n, (imya, i, j, t) in enumerate(kuski):
        s = max(0, w[i]["start"] - a.pad)
        print(f"   seg-{n}  {s:5.1f}–{s + t:5.1f} с  {t:4.1f} с  {imya:16}  «{' '.join(x['text'] for x in w[i:j + 1])}»")
    print(f"   Лицо {lico_s:.1f} с = {100 * lico_s / dur:.0f}% ролика (норма 20–30%) · ≈{kr_lico} кр.")
    print(f"\n3) Б-РОЛЛЫ — всё остальное ({dur - lico_s:.1f} с), под тем же сплошным голосом.")
    print(f"\nИтого ≈{kr_golos + kr_lico} кр. (весь ролик на лице было бы ≈{math.ceil(dur * kr_min / 60)} кр.). Точно — остаток до/после.")
    specs = " ".join(f'"{spec(w, i, j)}"' for _, i, j, _ in kuski)
    print(f"\nНарезка после голоса: montazh инструменты/segs.py --track {a.track} --words {a.words or 'words.json'} --out lico --pad {a.pad} {specs}")
    if a.papka:
        f = pathlib.Path(a.papka) / "plan-lica.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"dlitelnost": round(dur, 2), "otkuda": otkuda, "model": m, "engine": eng,
                                 "golos": {"voice": voice, "engine_settings": DVIZHOK_GOLOSA.get(lang), "speed": SKOROST,
                                           "engine": "avatar_iii", "kredity": kr_golos},
                                 "kuski": [{"rol": k[0], "spec": spec(w, k[1], k[2]), "sek": round(k[3], 2)} for k in kuski],
                                 "dolya": round(100 * lico_s / dur, 1), "kredity_lico": kr_lico}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        print(f"записал {f}", file=sys.stderr)


# ---------- загрузка кусков ----------
def kuski_mp3(papka):
    f = sorted(pathlib.Path(papka).glob("seg-*.mp3"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    if not f:
        sys.exit(f"В {papka} нет seg-N.mp3: сначала montazh segs.py. HeyGen берёт mp3, m4a — нет.")
    return f


def zagruzka(a):
    files = [{"filename": f.name, "content_type": "audio/mpeg", "size_bytes": f.stat().st_size} for f in kuski_mp3(a.papka)]
    print(json.dumps({"create_asset_upload_batch": {"title": "куски лица", "files": files}, "zametki": [
        "Ответ коннектора целиком сохрани в ПАПКА/zagruzka.json, потом: heygen.py put ПАПКА/zagruzka.json --papka ПАПКА.",
        "Загрузка бесплатная: кредиты тратит только create_video_from_avatar."]}, ensure_ascii=False, indent=2))


def obkhod(d):
    if isinstance(d, dict):
        yield d
        for v in d.values():
            yield from obkhod(v)
    elif isinstance(d, list):
        for v in d:
            yield from obkhod(v)


def najti_aktivy(d):
    """(имя файла, asset_id) из ответа create_asset_upload_batch / get_asset_batch, в порядке seg-N."""
    # ответ create_asset_upload_batch: items[] в порядке запроса, без имён файлов (проверено 22.11.2026)
    zap = [x for x in obkhod(d) if x.get("upload_url") or x.get("asset_id") or x.get("video_id")]
    out = [(x.get("filename") or f"seg-{n}.mp3", x.get("asset_id") or x.get("video_id") or x.get("id")) for n, x in enumerate(zap)]
    out = [(f, aid) for f, aid in out if aid]
    if not out:
        sys.exit("В ответе не нашёл asset_id. Сохрани ответ create_asset_upload_batch целиком, без пересказа.")
    return sorted(out, key=lambda p: int(re.sub(r"\D", "", p[0]) or 0))


def put(a):
    d = json.loads(pathlib.Path(a.otvet).read_text(encoding="utf-8"))
    fayly = {f.name: f for f in kuski_mp3(a.papka)}
    zapisi = [x for x in obkhod(d) if x.get("upload_url")]
    if not zapisi:
        sys.exit("В ответе нет upload_url. Нужен ответ create_asset_upload_batch целиком.")
    for n, x in enumerate(zapisi):
        f = fayly.get(x.get("filename") or "") or list(fayly.values())[n]  # items идут в порядке файлов запроса
        zag = x.get("upload_headers") or x.get("headers") or {}
        if isinstance(zag, list):
            zag = {h.get("name") or h.get("key"): h.get("value") for h in zag}
        zag = {k: str(v) for k, v in zag.items()}
        if not any(k.lower() == "content-type" for k in zag):
            zag["Content-Type"] = "audio/mpeg"
        req = urllib.request.Request(x["upload_url"], data=f.read_bytes(), method="PUT", headers=zag)
        with urllib.request.urlopen(req, timeout=300) as r:
            if r.status not in (200, 201, 204):
                sys.exit(f"{f.name}: загрузка вернула {r.status}")
        print(f"✓ {f.name} загружен")
    bid = next((x.get("batch_id") or x.get("batchId") for x in obkhod(d) if x.get("batch_id") or x.get("batchId")), "<batch_id>")
    print(f"Дальше: complete_asset_batch batchId={bid} → get_asset_batch, пока все completed → heygen.py lico --aktivy {a.otvet}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("nastroit")
    p.add_argument("--gruppy", required=True); p.add_argument("--golosa"); p.add_argument("--gruppa"); p.add_argument("--look")
    p.add_argument("--lang", default="ky"); p.add_argument("--model", choices=MODELI, default="6turbo")
    for imya in ("test", "golos"):
        p = sub.add_parser(imya)
        p.add_argument("--avatar", dest="look"); p.add_argument("--voice"); p.add_argument("--lang")
        p.add_argument("--skorost", type=float, default=SKOROST); p.add_argument("--model", choices=MODELI)
        p.add_argument("--format", choices=FORMAT, default="vertical"); p.add_argument("--papka"); p.add_argument("--tekst")
    p = sub.add_parser("lico")
    p.add_argument("--avatar", dest="look"); p.add_argument("--audio"); p.add_argument("--aktivy"); p.add_argument("--model", choices=MODELI)
    p.add_argument("--format", choices=FORMAT, default="vertical"); p.add_argument("--papka")
    p = sub.add_parser("temp"); p.add_argument("srt"); p.add_argument("--lang")
    p = sub.add_parser("slova"); p.add_argument("srt"); p.add_argument("--k", type=float, default=1.0); p.add_argument("--out")
    p = sub.add_parser("uskorit"); p.add_argument("mp3"); p.add_argument("--k", type=float, required=True)
    p = sub.add_parser("plan")
    p.add_argument("--tekst"); p.add_argument("--words"); p.add_argument("--dolya", type=float, default=25)
    p.add_argument("--start", type=float, default=0, choices=(0, 3)); p.add_argument("--pad", type=float, default=0.4)
    p.add_argument("--lang"); p.add_argument("--model", choices=MODELI); p.add_argument("--papka")
    p.add_argument("--track", default="golos.mp3", help="сплошной голос (после ускорения — golos-xK.mp3)")
    p = sub.add_parser("zagruzka"); p.add_argument("papka")
    p = sub.add_parser("put"); p.add_argument("otvet"); p.add_argument("--papka", required=True)
    a = ap.parse_args()
    if not 0.5 <= getattr(a, "skorost", 1.0) <= 1.5:
        sys.exit("Скорость HeyGen — от 0.5 до 1.5.")
    if a.cmd == "plan" and not (a.tekst or a.words):
        sys.exit("plan: нужен --tekst (оценка) или --words (точно).")
    {"nastroit": nastroit, "test": test, "golos": golos, "lico": lico, "temp": temp, "slova": slova, "uskorit": uskorit,
     "plan": plan, "zagruzka": zagruzka, "put": put}[a.cmd](a)


if __name__ == "__main__":
    main()
