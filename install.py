"""Установка контент-завода — Mac и Windows, без прав администратора. Запускает Claude Code (см. УСТАНОВКА.md).

  py install.py                                   всё: монтаж, парсер, карусели
  py install.py --chasti montazh,parser           только эти части: montazh, parser, karuseli, bot
  py install.py --light                           монтаж без полных библиотек анимаций (~90 МБ вместо ~0,5 ГБ)
  py install.py --light --bez-paka                слабый интернет: без пака звуков и карты, их докачает повторный запуск без флага
  (Mac: python3 вместо py; через пакет «Умный Claude»: sh "$HOME/.claude/umnyi/bin/py" install.py …)

Код завода живёт в ~/.claude/skills/zavod и обновляется git pull. Данные человека — только в Projects/завод
(local.md, планы/, ролики/, креатив/, медиатека/, конкуренты/), ключи — в ~/.claude/.env. Обновление их не трогает.
Повторный запуск безопасен: доставляет недостающее, ничего не удаляет. Проверка после установки — proverka.py.
"""
import argparse, os, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z

SKILLS = ROOT.parent
REPOS = {"montazh": "https://github.com/neuroakyl/neuroakyl-montazh", "parser": "https://github.com/neuroakyl/instagram-parser"}
DIRS = {"montazh": "montazh", "parser": "instagram-parser"}
KLYUCHI = ["KIE_API_KEY", "BUFFER_API_KEY", "APIFY_TOKEN", "GEMINI_API_KEY", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY", "TELEGRAM_BOT_TOKEN"]

ap = argparse.ArgumentParser()
ap.add_argument("--chasti", default="montazh,parser,karuseli")
ap.add_argument("--light", action="store_true")
ap.add_argument("--bez-paka", action="store_true")
ap.add_argument("--istochnik", help="для теста: папка с локальными копиями репозиториев вместо GitHub")
a = ap.parse_args()
want = [x.strip() for x in a.chasti.split(",") if x.strip()]
bad = []


def ok(m): print(f"  ✓ {m}", flush=True)
def warn(m): print(f"  ! {m}", flush=True)
def err(m): print(f"  ✗ {m}", flush=True); bad.append(m)


def git(*args, popytok=3):
    """git с повтором: на слабом интернете клон рвётся, вторая попытка обычно проходит."""
    r = None
    for i in range(popytok):
        r = subprocess.run(["git", *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            return r
        time.sleep(3 * (i + 1))
    return r


print("1. Пакет «Умный Claude» и папки человека")
if (Z.HOME / ".claude" / "umnyi").exists():
    ok("«Умный Claude» стоит: мозг, правила и ключи — общие")
else:
    warn("«Умный Claude» не стоит — завод работает и без него, но лучше поставить его первым (урок 2)")
zv = Z.zavod()
for d in Z.PODPAPKI:
    (zv / d).mkdir(parents=True, exist_ok=True)
lm = zv / "local.md"
if lm.exists():
    ok(f"настройки: {lm} уже есть, не трогаю")
elif (ROOT / "local.md").exists():  # старое место — переносим к человеку
    shutil.move(str(ROOT / "local.md"), lm)
    ok(f"настройки перенесены из папки навыка в {lm}")
else:
    shutil.copy(ROOT / "local.example.md", lm)
    ok(f"настройки: создан {lm}")
ok(f"рабочая папка завода: {zv}")
onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
if onedrive and str(zv).lower().startswith(onedrive.lower()):
    warn("папка завода внутри OneDrive: рендер может ломаться. Перенеси Projects в домашнюю папку (урок 1)")

print("2. Ключи (~/.claude/.env)")
env = Z.CLAUDE_ENV
env.parent.mkdir(parents=True, exist_ok=True)
est = env.read_text(encoding="utf-8-sig").splitlines() if env.exists() else []
imena = {s.split("=", 1)[0].strip() for s in est if "=" in s}
nado = [k for k in KLYUCHI if k not in imena]
if nado:  # дописываем только имена; значения вставляет человек, Claude файл не читает
    with env.open("a", encoding="utf-8") as f:
        f.write(("\n" if est and est[-1].strip() else "") + "\n".join(f"{k}=" for k in nado) + "\n")
    ok(f"в файл ключей добавлены пустые строки: {', '.join(nado)}")
else:
    ok("файл ключей на месте, строки для завода есть")
if (ROOT / ".env").exists():
    warn("в папке навыка остался старый .env — ключи читаются и оттуда, но переложи их в ~/.claude/.env")
if (ROOT / ".git").exists() and shutil.which("git"):
    subprocess.run(["git", "-C", str(ROOT), "config", "core.hooksPath", ".githooks"], capture_output=True)

print("3. Части завода")
if not shutil.which("git") and (set(want) & set(REPOS)):
    sys.exit("нет git: Mac — `xcode-select --install`; Windows — `winget install --id Git.Git -e --source winget`. "
             "Потом перезапусти приложение Claude и запусти install.py ещё раз.")
for part in want:
    if part in REPOS:
        dst = SKILLS / DIRS[part]
        src = str(pathlib.Path(a.istochnik) / DIRS[part]) if a.istochnik else REPOS[part]
        if (dst / ".git").exists():
            r = git("-C", dst, "pull", "--ff-only")
            ok(f"{part}: обновлён") if r.returncode == 0 else err(f"{part}: git pull не прошёл: {r.stderr.strip()[:200]}")
        elif dst.exists():
            ok(f"{part}: уже лежит в {dst} (не git — не обновляю)")
        else:
            r = git("clone", "--depth", "1", src, dst)
            ok(f"{part}: скачан в {dst}") if r.returncode == 0 else err(f"{part}: не скачался ({src}): {r.stderr.strip()[:200]}")
    elif part == "karuseli":
        ok("карусели: нужен только Node (ставит монтаж), браузер для картинок скачается при первой карусели")
    elif part == "bot":
        ok("бот: ставится по модули/бот.md (нужен Bun и токен от @BotFather) — это урок 7")
    else:
        err(f"нет такой части: {part}")

if "montazh" in want and (SKILLS / "montazh" / "install.py").exists():
    print("4. Монтаж: программы и пакеты (5–20 минут, один раз)" + (" — без пака, слабый интернет" if a.bez_paka else ""))
    cmd = [sys.executable, "-X", "utf8", "install.py"] + (["--light"] if a.light else []) + (["--bez-paka"] if a.bez_paka else [])
    if subprocess.run(cmd, cwd=SKILLS / "montazh").returncode:
        err("монтаж: установщик упал, смотри строки с ✗ выше; повторный запуск докачает с места")
    ml = SKILLS / "montazh" / "local.md"  # ролики монтажа — в папку завода, а не в «Документы» (OneDrive)
    if ml.exists():
        s = ml.read_text(encoding="utf-8")
        if "~/Videos/монтаж/" in s:
            ml.write_text(s.replace("`~/Videos/монтаж/`", f"`{(zv / 'ролики').as_posix()}/`"), encoding="utf-8")
            ok(f"монтаж складывает ролики в {zv / 'ролики'}")

print()
if bad:
    print("Есть ошибки:")
    for b in bad:
        print(" -", b)
    sys.exit(1)
print("Готово: части завода на месте. Дальше — проверка: proverka.py (УСТАНОВКА.md, шаг 4).")
