"""Креативный ролик без рук: кадры и клипы по API Kie, смета, лимит денег, сборка в монтаж. Mac и Windows, только Python.

  python3 -I kreativ.py new ПАПКА [--format vertical|horizontal]      папки проекта и пустой proekt.json
  python3 -I kreativ.py smeta ПАПКА                                   что запустится и сколько стоит. Ничего не тратит
  python3 -I kreativ.py geroi ПАПКА --da КРЕДИТЫ                      образы героев (--da — потолок на этот запуск)
  python3 -I kreativ.py kadry ПАПКА --da КРЕДИТЫ                      ключевые кадры + лист kadry/_list.jpg на проверку
  python3 -I kreativ.py klipy ПАПКА --da КРЕДИТЫ                      анимация кадров, где klip: true
  python3 -I kreativ.py sobrat ПАПКА --dvizhok ПАПКА_ДВИЖКА           клипы, голос, музыку — в композицию Klipy
  --zanovo 03,07 перегенерировать эти кадры · --fake бесплатная пробная прогонка на заглушках

Деньги: без --da генерации нет; потолок проверяется до запуска по смете и после каждой задачи по настоящему балансу.
Запреты: промпт с запретным образом не уйдёт в генерацию (ZAPRET ниже + zaprety в proekt.json).
Обрыв: id задачи пишется сразу, повторный запуск дожидается её, а не платит второй раз.
"""
import argparse, concurrent.futures as cf, json, os, pathlib, re, shutil, ssl, subprocess, sys, tempfile, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z  # ключи из ~/.claude/.env, ffmpeg из монтажа, UTF-8 на Windows
USD = 0.005  # 1 кредит Kie, kie.ai/pricing
API = "https://api.kie.ai/api/v1"
UPLOAD = "https://kieai.redpandaai.co/api/file-stream-upload"
SIZE = {"vertical": ("9:16", 720, 1280), "horizontal": ("16:9", 1280, 720)}

# Цены в кредитах (kie.ai/pricing и наш журнал расхода, 07.11.2026). Настоящий расход считается по балансу, это только смета.
KARTINKI = {
    "nano-banana-2": {"1K": 8, "2K": 12, "4K": 18},
    "nano-banana-pro": {"1K": 18, "2K": 18, "4K": 24},
}
KLIPY = {  # кредитов за секунду; (разрешение, звук)
    "bytedance/seedance-2-fast": {("480p", False): 7, ("720p", False): 15, ("480p", True): 7, ("720p", True): 15},
    "bytedance/seedance-2": {("480p", False): 12, ("720p", False): 25, ("480p", True): 12, ("720p", True): 25},
    "kling-3.0/video": {("std", False): 15.1, ("std", True): 22.7, ("pro", False): 20.2, ("pro", True): 30.2},
}
# kod — клипы не генерируем, картинку двигает монтаж (самое дешёвое); klip: true у важных кадров всё равно уйдёт в модель связки
SVYAZKI = {
    "kod": dict(kartinka="nano-banana-2", kachestvo="2K", klip="bytedance/seedance-2-fast", razreshenie="480p"),
    "deshevo": dict(kartinka="nano-banana-2", kachestvo="2K", klip="bytedance/seedance-2-fast", razreshenie="480p"),
    "baza": dict(kartinka="nano-banana-pro", kachestvo="2K", klip="kling-3.0/video", razreshenie="std"),
    "kachestvo": dict(kartinka="nano-banana-pro", kachestvo="4K", klip="bytedance/seedance-2", razreshenie="720p"),
}
# Религиозный запрет: пророков и Всевышнего не изображаем ни в одном проекте, настройкой не снимается
ZAPRET = r"пророк|мухамм[аеу]д|мухаммад|магомет|ﷺ|пайгамбар|prophet|muhamm[ae]d|mohamm[ae]d|allah|аллах|кудай"


def load(p):
    return json.loads((p / "proekt.json").read_text(encoding="utf-8"))


def key():
    return Z.kluch("KIE_API_KEY", "kie.ai → API Key")


def http(url, body=None):
    head = {"Authorization": f"Bearer {key()}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, head)
    try:
        return json.load(urllib.request.urlopen(req, timeout=90))
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError):
            raise
    # Python с python.org на Mac часто без корневых сертификатов: тогда через системный curl
    cmd = ["curl", "-sS", "-m", "90", url, "-H", f"Authorization: Bearer {key()}", "-H", "Content-Type: application/json"]
    return json.loads(subprocess.run(cmd + (["-d", json.dumps(body)] if body else []), capture_output=True, text=True).stdout)


def balance():
    return float(http(f"{API}/chat/credit")["data"])


def upload(f):
    # файл через стандартный ввод: путь с кириллицей не попадает в команду curl (Windows curl.exe)
    with open(f, "rb") as fh:
        out = subprocess.run(["curl", "-sS", "-X", "POST", UPLOAD, "-H", f"Authorization: Bearer {key()}",
                              "-F", f"file=@-;filename=ref{pathlib.Path(f).suffix.lower()}", "-F", "uploadPath=images/zavod"],
                             stdin=fh, capture_output=True).stdout.decode("utf-8", "replace")
    return json.loads(out)["data"]["downloadUrl"]


def check_zapret(pr):
    extra = [z for z in pr.get("zaprety", []) if z.strip()]
    pat = re.compile("|".join([ZAPRET] + [re.escape(z) for z in extra]), re.I)
    bad = []
    for g in pr.get("geroi", []):
        if pat.search(g.get("promt", "") + " " + g.get("opisanie", "")):
            bad.append(f"герой {g['id']}")
    for k in pr.get("kadry", []):
        if pat.search(k.get("promt", "") + " " + k.get("dvizhenie", "")):
            bad.append(f"кадр {k['id']}")
    if bad:
        sys.exit("✗ запрещённый образ в промпте: " + ", ".join(bad) + ". Перепиши: показывать через предметы, места, руки, спину — не лицо и не фигуру.")


def svyazka(pr):
    return {**SVYAZKI[pr.get("svyazka", "baza")], **pr.get("modeli", {})}


def cena_kartinki(s):
    return KARTINKI[s["kartinka"]][s["kachestvo"]]


def cena_klipa(s, sek, zvuk):
    return KLIPY[s["klip"]][(s["razreshenie"], bool(zvuk))] * sek


CLEAN = re.compile(r"[^a-z0-9а-яёңөүәіұқғһ-]")


def slovo(words, text, after=0.0):
    raw, _, nth = text.partition("#")
    k = CLEAN.sub("", raw.lower())
    hits = [w for w in words if w["start"] >= after - 0.01 and CLEAN.sub("", w["text"].lower()).startswith(k)]
    if len(hits) < int(nth or 1):
        sys.exit(f"слово не найдено в голосе: {text}")
    return hits[int(nth or 1) - 1]["start"]


def mesta(p, pr):
    """Сколько секунд кадр стоит на экране: по слову голоса (s_slova), без голоса — его dlina. Возвращает [(начало, длина)]."""
    f = p / "golos" / "words.json"
    words = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    starts, t = [], 0.0
    for i, k in enumerate(pr["kadry"]):
        if words and i and k.get("s_slova"):
            t = slovo(words, k["s_slova"], t)
        starts.append(t)
        t += k.get("dlina", 4)
    end = words[-1]["end"] + 0.9 if words else t
    return [(a, (starts[i + 1] if i + 1 < len(starts) else end) - a) for i, a in enumerate(starts)]


def dlina_klipa(mesto):
    return max(4, min(15, int(mesto + 0.99)))  # 4–15 с: границы Seedance 2 и Kling 3.0 по их документации


def nuzhny_klipy(pr):
    return [k for k in pr["kadry"] if k.get("klip", pr.get("svyazka") != "kod")]


def smeta(p, a=None):
    pr = load(p)
    check_zapret(pr)
    s = svyazka(pr)
    done = lambda sub, x, ext: any((p / sub / f"{x}{e}").exists() for e in ext)
    g = [x for x in pr.get("geroi", []) if not done("geroi", x["id"], (".png", ".jpg"))]
    kd = [x for x in pr["kadry"] if not done("kadry", x["id"], (".png", ".jpg"))]
    kl = [x for x in nuzhny_klipy(pr) if not done("klipy", x["id"], (".mp4",))]
    cg, ck = len(g) * cena_kartinki(s), len(kd) * cena_kartinki(s)
    mst = dict(zip((x["id"] for x in pr["kadry"]), mesta(p, pr)))
    sek = {x["id"]: dlina_klipa(mst[x["id"]][1]) for x in kl}
    cv = sum(cena_klipa(s, sek[x["id"]], x.get("zvuk")) for x in kl)
    total = cg + ck + cv
    print(f"связка {pr.get('svyazka', 'baza')}: кадры {s['kartinka']} {s['kachestvo']}, клипы {s['klip']} {s['razreshenie']}")
    print(f"  героев {len(g)} × {cena_kartinki(s)} кр = {cg:.0f} кр")
    print(f"  кадров {len(kd)} × {cena_kartinki(s)} кр = {ck:.0f} кр")
    print(f"  клипов {len(kl)}, {sum(sek.values())} с = {cv:.0f} кр")
    print(f"ИТОГО {total:.0f} кр ≈ ${total * USD:.2f} за один проход. Перегенерации сверху: закладывай ×2.")
    return {"geroi": cg, "kadry": ck, "klipy": cv}


class Kassa:
    """Потолок на запуск: до старта по смете, во время работы по настоящему балансу."""

    def __init__(self, da, fake):
        self.da, self.fake = da, fake
        self.start = None if fake else balance()

    def spent(self):
        return 0 if self.fake else self.start - balance()

    def check(self):
        if self.spent() > self.da:
            sys.exit(f"✗ стоп: потрачено {self.spent():.0f} кр, потолок {self.da:.0f} кр. Новые задачи не запускаю.")


def zapros(p, name, model, vhod, out, fake, kassa):
    """Создать задачу (или дождаться уже созданной), скачать результат в out. Возвращает путь."""
    if fake:
        return zaglushka(p, name, out)
    state = p / "zadachi.json"
    st = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
    tid = st.get(name)
    if not tid:
        kassa.check()
        d = http(f"{API}/jobs/createTask", {"model": model, "input": vhod})
        if d.get("code") != 200:
            sys.exit(f"✗ {name}: Kie не принял задачу: {d.get('msg') or d}")
        tid = d["data"]["taskId"]
        st = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
        st[name] = tid
        state.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {name}: задача {tid}", flush=True)
    while True:
        time.sleep(8)
        info = http(f"{API}/jobs/recordInfo?taskId={tid}")["data"]
        if info["state"] in ("success", "fail"):
            break
    st = json.loads(state.read_text(encoding="utf-8"))
    st.pop(name, None)
    state.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    if info["state"] == "fail":
        print(f"  ✗ {name}: {info.get('failMsg')}", flush=True)
        return None
    url = json.loads(info["resultJson"])["resultUrls"][0]
    dst = out.with_suffix(pathlib.Path(url.split("?")[0]).suffix or out.suffix)
    subprocess.run(["curl", "-sSL", "-o", str(dst), url], check=True)
    with (p / "rashod.log").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%F %T')}\t{model}\t{name}\t{kassa.spent():.0f} кр всего\n")
    print(f"  ✓ {dst.name}", flush=True)
    return dst


def zaglushka(p, name, out):
    fmt = load(p).get("format", "vertical")
    _, w, h = SIZE[fmt]
    if out.suffix == ".mp4":
        src = ["-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration=4", "-pix_fmt", "yuv420p"]
    else:
        src = ["-f", "lavfi", "-i", f"gradients=size={w}x{h}:n=3:seed={abs(hash(name)) % 999}", "-frames:v", "1"]
    subprocess.run([Z.programma("ffmpeg"), "-v", "error", "-y"] + src + [str(out)], check=True)
    print(f"  ~ {out.name} (заглушка)", flush=True)
    return out


def refs(p, ids, fake):
    """Ссылки на референсы: id героя, kadr:ID или путь к своему фото. Загруженное живёт у Kie 24 часа, поэтому каждый запуск заново."""
    pr, files = load(p), []
    for r in ids:
        g = next((x for x in pr.get("geroi", []) if x["id"] == r), None)
        if g:
            files += [pathlib.Path(f) for f in g.get("foto", [])]
            files += [f for e in (".png", ".jpg", ".jpeg") for f in [p / "geroi" / f"{r}{e}"] if f.exists()]
        elif r.startswith("kadr:"):
            files += [f for e in (".png", ".jpg", ".jpeg") for f in [p / "kadry" / f"{r[5:]}{e}"] if f.exists()]
        else:
            files.append(p / r if not pathlib.Path(r).is_absolute() else pathlib.Path(r))
    return [] if fake else [upload(f) for f in files[:8]]  # больше 8 модель картинок не принимает


def vzyat(p, a, what, smeta_chast):
    if a.fake:
        return Kassa(0, True)
    if a.da is None:
        sys.exit(f"без --da не запускаю. Смета на этот шаг: {smeta_chast:.0f} кр ≈ ${smeta_chast * USD:.2f}. Сумму называет человек.")
    if smeta_chast > a.da:
        sys.exit(f"✗ {what}: смета {smeta_chast:.0f} кр больше потолка {a.da:.0f} кр. Подними потолок или убери кадры.")
    k = Kassa(a.da, False)
    if k.start < smeta_chast:
        sys.exit(f"✗ на балансе {k.start:.0f} кр, нужно {smeta_chast:.0f} кр: пополни kie.ai или возьми связку дешевле.")
    return k


def zanovo(p, sub, ids):
    for i in ids:
        for f in (p / sub).glob(f"{i}.*"):
            f.rename(f.with_name(f"{f.stem}_{int(time.time())}{f.suffix}"))  # старое не стираем: вдруг было лучше


def kartinka(p, pr, s, name, prompt, ref_ids, sub, a, kassa):
    aspect = SIZE[pr.get("format", "vertical")][0]
    stil = pr.get("stil", "")
    vhod = {"prompt": f"{stil}\n{prompt}".strip(), "image_input": refs(p, ref_ids, a.fake), "aspect_ratio": aspect,
            "resolution": s["kachestvo"], "output_format": "png"}
    return zapros(p, name, s["kartinka"], vhod, p / sub / f"{name}.png", a.fake, kassa)


def geroi(p, a):
    pr = load(p)
    chast = smeta(p)["geroi"]
    kassa, s = vzyat(p, a, "герои", chast), svyazka(pr)
    if a.zanovo:
        zanovo(p, "geroi", a.zanovo.split(","))
    with cf.ThreadPoolExecutor(3) as ex:
        # свои фото героя (поле foto) — главный референс лица: без них образ выходит «не похож»
        list(ex.map(lambda g: kartinka(p, pr, s, g["id"], g.get("promt") or g["opisanie"],
                                       g.get("refy") or ([g["id"]] if g.get("foto") else []), "geroi", a, kassa),
                    [g for g in pr.get("geroi", []) if not list((p / "geroi").glob(g["id"] + ".*"))]))


def kadry(p, a):
    pr = load(p)
    if a.zanovo:
        zanovo(p, "kadry", a.zanovo.split(","))
    chast = smeta(p)["kadry"]
    kassa, s = vzyat(p, a, "кадры", chast), svyazka(pr)
    todo = [k for k in pr["kadry"] if not list((p / "kadry").glob(k["id"] + ".*"))]
    with cf.ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda k: kartinka(p, pr, s, k["id"], k["promt"], k.get("geroi", []) + k.get("refy", []), "kadry", a, kassa), todo))
    fs = sorted(f for f in (p / "kadry").glob("*") if f.suffix in (".png", ".jpg") and "_" not in f.stem)
    if fs:
        w = 360 if pr.get("format") != "horizontal" else 480
        lst = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        lst.write("".join(f"file '{f.as_posix()}'\n" for f in fs))
        lst.close()
        subprocess.run([Z.programma("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst.name, "-frames:v", "1",
                        "-vf", f"scale={w}:-2,tile={min(len(fs), 5)}x{(len(fs) + 4) // 5}:padding=6", str(p / "kadry" / "_list.jpg")], check=True)
        os.unlink(lst.name)
        print("лист на проверку:", p / "kadry" / "_list.jpg")


def klipy(p, a):
    pr = load(p)
    if a.zanovo:
        zanovo(p, "klipy", a.zanovo.split(","))
    chast = smeta(p)["klipy"]
    kassa, s = vzyat(p, a, "клипы", chast), svyazka(pr)
    aspect = SIZE[pr.get("format", "vertical")][0]
    mst = dict(zip((x["id"] for x in pr["kadry"]), mesta(p, pr)))

    def odin(k):
        kadr = next((f for f in (p / "kadry").glob(k["id"] + ".*")), None)
        if not kadr:
            sys.exit(f"нет кадра {k['id']}: сначала шаг kadry")
        first = "" if a.fake else upload(kadr)
        sek = dlina_klipa(mst[k["id"]][1])
        move = k.get("dvizhenie") or k["promt"]
        if s["klip"].startswith("kling"):
            vhod = {"prompt": move, "image_urls": [first], "sound": bool(k.get("zvuk")), "duration": str(sek), "aspect_ratio": aspect,
                    "mode": s["razreshenie"], "multi_shots": False}
        else:
            vhod = {"prompt": move, "first_frame_url": first, "generate_audio": bool(k.get("zvuk")), "resolution": s["razreshenie"],
                    "aspect_ratio": aspect, "duration": sek}
        return zapros(p, k["id"], s["klip"], vhod, p / "klipy" / f"{k['id']}.mp4", a.fake, kassa)

    todo = [k for k in nuzhny_klipy(pr) if not (p / "klipy" / f"{k['id']}.mp4").exists()]
    with cf.ThreadPoolExecutor(3) as ex:
        res = list(ex.map(odin, todo))
    if not all(res):
        print("часть клипов упала: за упавшие Kie не списывает, запусти шаг ещё раз")
    if not a.fake:
        print(f"потрачено за запуск: {kassa.spent():.0f} кр ≈ ${kassa.spent() * USD:.2f}")


def sobrat(p, a):
    pr = load(p)
    dv = pathlib.Path(a.dvizhok)
    if not (dv / "src" / "montazh.json").exists():
        sys.exit(f"{dv}: это не папка движка. Скопируй шаблон монтажа (движки.md, «Новый ролик»).")
    pub = dv / "public" / "klipy"
    pub.mkdir(parents=True, exist_ok=True)
    golos = next((f for f in [p / "golos" / "voice.wav", p / "golos" / "voice.mp3"] if f.exists()), None)
    if golos:
        shutil.copy(golos, dv / "public" / f"voice{golos.suffix}")
    words = (p / "golos" / "words.json").exists()
    if words:
        shutil.copy(p / "golos" / "words.json", dv / "src" / "words.json")
    mst = mesta(p, pr)
    out = []
    for i, k in enumerate(pr["kadry"]):
        nado = mst[i][1]
        klip = p / "klipy" / f"{k['id']}.mp4"
        kadr = next((f for f in (p / "kadry").glob(k["id"] + ".*") if "_" not in f.stem), None)
        src = klip if klip.exists() else kadr
        if not src:
            sys.exit(f"нет ни клипа, ни кадра {k['id']}")
        shutil.copy(src, pub / src.name)
        el = {"src": f"klipy/{src.name}", "perehod": k.get("perehod", "cut"), "kamera": k.get("kamera", "in" if src.suffix != ".mp4" else "none")}
        if src.suffix == ".mp4":
            d = float(subprocess.run([Z.programma("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                                     capture_output=True, text=True).stdout)
            # клип короче места — замедляем (не сильнее 0,6), длиннее — режем хвост
            if d / nado < 0.6:  # иначе склейки уедут от слов
                sys.exit(f"кадр {k['id']}: клип {d:.1f} с, а на экране он {nado:.1f} с. Раздели кадр на два или перегенерируй: --zanovo {k['id']}")
            sk = round(min(1.0, d / nado), 3)
            el.update({"ot": 0, "do": round(min(d, nado * sk), 3), "skorost": sk, "zvuk": bool(k.get("zvuk"))})
        else:
            el["dlit"] = round(nado, 3)
        out.append(el)
    muzyka = next((f for f in (p / "muzyka").glob("*") if f.suffix in (".mp3", ".wav", ".m4a")), None)
    if muzyka:
        shutil.copy(muzyka, dv / "public" / f"music{muzyka.suffix}")
    m = {"format": pr.get("format", "vertical"), "klipy": out, "golos": f"voice{golos.suffix}" if golos else None,
         "muzyka": f"music{muzyka.suffix}" if muzyka else None, "muzykaDb": -22, "subtitry": words and pr.get("subtitry", True)}
    (dv / "src" / "montazh.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"монтаж собран: {len(out)} кусков, {sum(e.get('dlit') or (e['do'] - e['ot']) / e.get('skorost', 1) for e in out):.1f} с. Рендер: COMP=Klipy node render.mjs final.mp4")


def new(p, a):
    for sub in ("referensy", "geroi", "kadry", "klipy", "golos", "muzyka", "final"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    f = p / "proekt.json"
    if f.exists():
        sys.exit(f"{f} уже есть, не трогаю")
    f.write_text(json.dumps({
        "nazvanie": p.name, "format": a.format, "svyazka": "baza", "tip": "razovyy", "stil": "", "zaprety": [], "subtitry": True,
        "geroi": [{"id": "geroy", "opisanie": "", "promt": "", "foto": []}],
        "kadry": [{"id": "01", "rol": "hook", "tekst": "", "s_slova": "", "promt": "", "dvizhenie": "", "geroi": ["geroy"], "dlina": 4, "klip": True, "perehod": "cut"}],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("проект:", p)


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("cmd", choices=["new", "smeta", "geroi", "kadry", "klipy", "sobrat"])
ap.add_argument("papka")
ap.add_argument("--format", default="vertical", choices=list(SIZE))
ap.add_argument("--da", type=float)
ap.add_argument("--zanovo", default="")
ap.add_argument("--fake", action="store_true")
ap.add_argument("--dvizhok")
A = ap.parse_args()
{"new": new, "smeta": lambda p, a: smeta(p), "geroi": geroi, "kadry": kadry, "klipy": klipy, "sobrat": sobrat}[A.cmd](pathlib.Path(A.papka).resolve(), A)
