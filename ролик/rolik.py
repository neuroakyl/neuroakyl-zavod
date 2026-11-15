"""Ролик: папка, движок монтажа, черновик на заглушках. Mac и Windows, только стандартная библиотека.

  py rolik.py new "тема" [--tip bez-lica|avatar|zhivoe|kreativ] [--format vertical|horizontal]
        → Projects/завод/ролики/ГГГГ-ММ-ДД-тема/: ролик.json, сценарий.md, исходники/, движок/ (копия шаблона монтажа)
  py rolik.py zaglushka ПАПКА      черновик без денег и без ключей: голос-заглушка, кадры-заглушки, подписи → черновик.mp4
  py rolik.py render ПАПКА [ИМЯ]   рендер того, что лежит в движок/src/montazh.json → ПАПКА/ИМЯ.mp4

Заглушка проверяет весь путь (папки, движок, Node, ffmpeg, Remotion, подписи, рендер) — так ученик видит первый ролик до оплаты сервисов.
Настоящий ролик: голос — golos.py (ElevenLabs) или аватар HeyGen, кадры — broll.py / kreativ.py; модуль своего формата в `модули/`.
"""
import argparse, datetime, json, os, pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z

TIPY = {"bez-lica": "без лица: голос + Б-роллы", "avatar": "аватар + Б-роллы", "zhivoe": "живая съёмка", "kreativ": "креатив на нейросетях"}
SIZE = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
SHABLON = Z.MONTAZH / "шаблон"
PROBA = ("Это первый ролик завода. Голос и кадры пока заглушки, зато весь путь настоящий: "
         "сценарий, подписи, монтаж и рендер. Дальше подключим твой голос и твои кадры.")


def slug(t):
    t = re.sub(r"[^\w\s-]", "", t.lower(), flags=re.U).strip()
    return re.sub(r"[\s_]+", "-", t)[:40] or "rolik"


def ssylka_na_papku(cel, gde):
    """node_modules движка — ссылкой на установленный шаблон (не качать 450 МБ на каждый ролик).
    Windows: junction (без прав администратора), Mac: symlink."""
    if gde.exists() or gde.is_symlink():
        return
    if Z.WIN:
        import _winapi
        _winapi.CreateJunction(str(cel), str(gde))
    else:
        gde.symlink_to(cel, target_is_directory=True)


def new(a):
    if not (SHABLON / "src" / "montazh.json").exists():
        sys.exit(f"нет движка монтажа ({SHABLON}): поставь его — `install.py --chasti montazh`")
    tema = " ".join(a.chto).strip() or "проба"
    p = Z.zavod() / "ролики" / f"{datetime.date.today().isoformat()}-{slug(tema)}"
    if p.exists():
        sys.exit(f"{p} уже есть")
    (p / "исходники").mkdir(parents=True)
    shutil.copytree(SHABLON, p / "движок", ignore=shutil.ignore_patterns("node_modules", "out", ".cache", "*.mp4"))
    ssylka_na_papku(SHABLON / "node_modules", p / "движок" / "node_modules")
    m = json.loads((p / "движок" / "src" / "montazh.json").read_text(encoding="utf-8"))
    m.update({"format": a.format, "klipy": []})
    (p / "движок" / "src" / "montazh.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "ролик.json").write_text(json.dumps({"tema": tema, "tip": a.tip, "format": a.format, "status": "сценарий"},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    (p / "сценарий.md").write_text(f"# {tema}\n\nФормат: {TIPY[a.tip]}, {a.format}.\n\n## Текст\n\n## Разметка под монтаж\n", encoding="utf-8")
    print(f"ролик: {p}\n  формат: {TIPY[a.tip]}, {a.format}\n  дальше: сценарий (модуль `сценарий.md`), потом путь формата из SKILL.md")


def ff(*args):
    subprocess.run([Z.programma("ffmpeg"), "-v", "error", "-y", *map(str, args)], check=True)


def tekst_scenariya(p):
    f = p / "сценарий.md"
    if not f.exists():
        return PROBA
    s = f.read_text(encoding="utf-8")
    if "## Текст" in s:
        s = s.split("## Текст", 1)[1].split("\n## ", 1)[0]
    s = " ".join(l.strip() for l in s.splitlines() if l.strip() and not l.lstrip().startswith(("#", "|", ">", "-")))
    return s or PROBA


def zaglushka(a):
    p = pathlib.Path(a.chto[0]).resolve() if a.chto else sys.exit("укажи папку ролика")
    info = json.loads((p / "ролик.json").read_text(encoding="utf-8"))
    dv, fmt = p / "движок", info.get("format", "vertical")
    w, h = SIZE[fmt]
    # 1. подписи: черновые тайминги по тексту сценария (как до озвучки в монтаже)
    t = p / "исходники" / "текст-для-заглушки.txt"
    t.write_text(tekst_scenariya(p), encoding="utf-8")
    subprocess.run([sys.executable, "-I", str(Z.MONTAZH / "инструменты" / "demo_words.py"), str(t), str(dv / "src" / "words.json")], check=True)
    words = json.loads((dv / "src" / "words.json").read_text(encoding="utf-8"))
    dlit = round(words[-1]["end"] + 0.6, 2)
    # 2. голос-заглушка: тихий тон на всю длину (настоящий — golos.py или аватар)
    ff("-f", "lavfi", "-i", f"sine=frequency=220:duration={dlit}", "-af", "volume=0.05", dv / "public" / "voice.wav")
    # 3. кадры-заглушки: «человек в кадре» для аватара и живой съёмки, Б-роллы для всех
    kl = dv / "public" / "klipy"
    kl.mkdir(parents=True, exist_ok=True)
    klipy, ostalos, i = [], dlit, 0
    lico = info.get("tip") in ("avatar", "zhivoe")
    while ostalos > 0.05:
        d = round(min(3.0, ostalos), 2)
        imya = f"zaglushka-{i:02d}.mp4"
        src = f"testsrc2=size={w}x{h}:rate=30:duration={d}" if (lico and i % 2 == 0) else \
            f"gradients=size={w}x{h}:rate=30:duration={d}:n=3:seed={i * 7 + 1}:speed=0.03"
        ff("-f", "lavfi", "-i", src, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", kl / imya)
        klipy.append({"src": f"klipy/{imya}", "ot": 0, "do": d, "zvuk": False, "perehod": "fade" if i else "cut", "kamera": "in"})
        ostalos, i = round(ostalos - d, 2), i + 1
    m = {"format": fmt, "klipy": klipy, "golos": "voice.wav", "muzyka": None, "muzykaDb": -22, "subtitry": True}
    (dv / "src" / "montazh.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"заглушка: {len(words)} слов, {dlit} с, {len(klipy)} кусков")
    render(a, imya="черновик")


def render(a, imya=None):
    p = pathlib.Path(a.chto[0]).resolve()
    imya = imya or (a.chto[1] if len(a.chto) > 1 else "видео")
    out = p / f"{imya}.mp4"
    env = dict(os.environ, COMP="Klipy")
    print("рендер (первый раз движок сам скачает браузер для рендера ~100 МБ)…", flush=True)
    r = subprocess.run([Z.programma("node"), "render.mjs", str(out)], cwd=p / "движок", env=env)
    if r.returncode or not out.exists():
        sys.exit("рендер не прошёл: смотри строки выше")
    d = subprocess.run([Z.programma("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True).stdout.strip()
    print(f"готово: {out} ({d} с, {out.stat().st_size // 1024} КБ)")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("cmd", choices=["new", "zaglushka", "render"])
ap.add_argument("chto", nargs="*")
ap.add_argument("--tip", default="bez-lica", choices=list(TIPY))
ap.add_argument("--format", default="vertical", choices=list(SIZE))
A = ap.parse_args()
{"new": new, "zaglushka": zaglushka, "render": render}[A.cmd](A)
