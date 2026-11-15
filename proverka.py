"""Проверка завода: что стоит, что работает, что подключить. Ничего не тратит и не меняет. Mac и Windows.

  py proverka.py            всё бесплатное: программы, папки, ключи (только есть / нет), движок
  py proverka.py --render   плюс черновой ролик на заглушках (~1–3 минуты): rolik.py new + zaglushka; --ostavit — не удалять файл

✓ работает · ✗ сломано (рядом — как починить) · ! не подключено или совет. В конце «ЗАВОД РАБОТАЕТ» или список поломок.
"""
import json, os, platform, shutil, subprocess, sys, tempfile, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z

lomki = []


def ok(m): print(f"✓ {m}", flush=True)
def warn(m): print(f"! {m}", flush=True)
def bad(m, kak): print(f"✗ {m}\n    как починить: {kak}", flush=True); lomki.append(m)


def zapusk(*cmd, **kw):
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", **{"timeout": 120, **kw})
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


print(f"Система: {platform.system()} {platform.release()} {platform.machine()}, Python {platform.python_version()}")
if sys.version_info < (3, 9):
    bad("Python старее 3.9", "Windows: winget install -e --id Python.Python.3.12 --scope user; Mac: xcode-select --install")
else:
    ok("Python")
ok("git") if shutil.which("git") else bad("нет git", "Windows: winget install --id Git.Git -e --source winget; Mac: xcode-select --install")

# папки и настройки
zv = Z.zavod()
if all((zv / d).is_dir() for d in Z.PODPAPKI) and (zv / "local.md").exists():
    ok(f"рабочая папка завода: {zv}")
else:
    bad(f"нет папки завода {zv} или её частей", "запусти install.py ещё раз")
for pole in ("Имя и ник", "Язык роликов"):
    if not Z.nastroika(pole):
        warn(f"в local.md не заполнено «{pole}» — спрошу при первом ролике")
mozg = Z.proekty() / "мозг"
n = len(list(mozg.glob("*.md"))) if mozg.exists() else 0
ok(f"мозг: {n} файлов") if n >= 5 else warn(f"мозг почти пустой ({n} файлов): сначала интервью (модуль мозг-интервью.md)")
if Z.WIN:
    s = str(zv)
    if any(x in s for x in ("OneDrive", "Рабочий стол", "Desktop")):
        warn("завод в OneDrive или на Рабочем столе: рендер может ломаться, лучше Projects в папке пользователя")
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem")
        if winreg.QueryValueEx(k, "LongPathsEnabled")[0] != 1:
            warn("длинные пути Windows выключены: если npm падает с «path too long» — включить LongPathsEnabled (нужен админ, делает человек)")
    except Exception:
        pass

# монтаж
m = Z.MONTAZH
if not (m / "SKILL.md").exists():
    bad("нет навыка монтажа", "install.py --chasti montazh")
else:
    for prog in ("ffmpeg", "ffprobe", "node"):
        p = shutil.which(prog, path=str(Z.venv_bin()) + os.pathsep + os.environ.get("PATH", ""))
        r = zapusk(p, "-version" if prog != "node" else "-v") if p else None
        ok(f"{prog}") if r and r.returncode == 0 else bad(f"{prog} не запускается", "install.py --chasti montazh (ставит в .venv монтажа)")
    nm = m / "шаблон" / "node_modules" / "remotion"
    ok("Remotion (движок рендера)") if nm.exists() else bad("нет пакетов Remotion", "install.py --chasti montazh")
    pak = m / "внешнее" / "пак" / "каталог.json"
    ok("пак монтажёра (звуки, переходы)") if pak.exists() else warn("пак монтажёра не скачан: ролики соберутся, позже — install.py без --bez-paka")
    if Z.WIN:
        warn("на Windows не работают вырезка человека на обложке и поиск лиц (только Mac): обложки — без вырезки")
ok("парсер Instagram") if (Z.SKILLS / "instagram-parser" / "insta.py").exists() or (Z.HOME / ".claude/skills/instagram-parser/insta.py").exists() \
    else warn("парсер Instagram не стоит (install.py --chasti parser) — нужен для разбора конкурентов")

# ключи: только есть / нет, значения не печатаются
nuzhno = {"KIE_API_KEY": "креатив (Kie)", "ELEVENLABS_API_KEY": "голос без лица (ElevenLabs)", "APIFY_TOKEN": "конкуренты (Apify)",
          "GEMINI_API_KEY": "расшифровка и кыргызский (Gemini, бесплатно)", "BUFFER_API_KEY": "выкладка (Buffer)",
          "TELEGRAM_BOT_TOKEN": "Telegram-бот"}
est = [v for k, v in nuzhno.items() if Z.est_kluch(k)]
net = [v for k, v in nuzhno.items() if not Z.est_kluch(k)]
ok(f"ключи заполнены: {', '.join(est)}") if est else warn("ни одного ключа пока нет — подключим по одному, когда понадобятся")
if net:
    warn(f"не подключено: {', '.join(net)}. Аватар HeyGen — коннектор claude.ai, ключ не нужен")
bun = shutil.which("bun") or (Z.HOME / ".bun" / "bin" / ("bun.exe" if Z.WIN else "bun")).exists()
ok("Bun (для Telegram-бота)") if bun else warn("Bun не стоит — нужен только для Telegram-бота (урок 7)")

# черновой ролик
if "--render" in sys.argv and not lomki:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="zavod-proverka-"))
    env = dict(os.environ, ZAVOD_PAPKA=str(tmp))
    r = zapusk(sys.executable, "-I", ROOT / "ролик" / "rolik.py", "new", "проверка", env=env)
    papka = next((tmp / "ролики").glob("*"), None) if r.returncode == 0 else None
    r = zapusk(sys.executable, "-I", ROOT / "ролик" / "rolik.py", "zaglushka", papka, env=env, timeout=1200) if papka else r
    f = papka / "черновик.mp4" if papka else None
    if f and f.exists() and f.stat().st_size > 100_000:
        ok(f"черновой ролик собрался: {f.stat().st_size // 1024} КБ, рендер работает")
        if "--ostavit" in sys.argv:
            print(f"  файл: {f}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)  # временная папка проверки, в Projects ничего не остаётся
    else:
        bad("черновой ролик не собрался", "покажи Claude строки ниже:\n" + (r.stdout + r.stderr)[-1500:])

print()
if lomki:
    print("ЕСТЬ ПОЛОМКИ: " + "; ".join(lomki))
    sys.exit(1)
print("ЗАВОД РАБОТАЕТ")
