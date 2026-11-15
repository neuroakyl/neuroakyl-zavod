"""Общее для скриптов завода: где папки человека, откуда ключи, где программы. Mac и Windows, только стандартная библиотека.

Контракт с пакетом «Умный Claude» (01_Обучение/система-ученика/структура.md):
  ключи      окружение → ~/.claude/.env → <завод>/.env (старое место, запасное)
  мозг       ~/Projects (или папка, которую пакет записал в ~/.claude/umnyi-sostoyanie.json) — переменная ZAVOD_PROEKTY перекрывает
  завод      <мозг>/завод: local.md, планы/, ролики/, креатив/, медиатека/, конкуренты/ — переменная ZAVOD_PAPKA перекрывает
  программы  ffmpeg, ffprobe, node из .venv монтажа (рядом с заводом) раньше системных
"""
import json, os, pathlib, platform, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent      # код завода (~/.claude/skills/zavod)
SKILLS = ROOT.parent
HOME = pathlib.Path.home()
WIN = platform.system() == "Windows"
CLAUDE_ENV = HOME / ".claude" / ".env"
MONTAZH = next((m for m in (pathlib.Path(os.environ.get("ZAVOD_MONTAZH", "")).expanduser() if os.environ.get("ZAVOD_MONTAZH") else None,
                             SKILLS / "montazh", HOME / ".claude" / "skills" / "montazh") if m and m.exists()), SKILLS / "montazh")
PODPAPKI = ("планы", "ролики", "креатив", "медиатека", "конкуренты")

for s in (sys.stdout, sys.stderr):  # Windows-консоль в cp1251 не роняет вывод с ✓ и кыргызскими буквами
    try:
        s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def proekty():
    if os.environ.get("ZAVOD_PROEKTY"):
        return pathlib.Path(os.environ["ZAVOD_PROEKTY"]).expanduser()
    try:
        p = json.loads((HOME / ".claude" / "umnyi-sostoyanie.json").read_text(encoding="utf-8")).get("proekty")
        if p:
            return pathlib.Path(p)
    except Exception:
        pass
    return HOME / "Projects"


def zavod():
    if os.environ.get("ZAVOD_PAPKA"):
        return pathlib.Path(os.environ["ZAVOD_PAPKA"]).expanduser()
    return proekty() / "завод"


def _iz_faila(f, name):
    try:
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].split(" #", 1)[0].strip().strip("\"'")
    except FileNotFoundError:
        pass
    return ""


def est_kluch(name):
    return bool(os.environ.get(name, "").strip() or _iz_faila(CLAUDE_ENV, name) or _iz_faila(ROOT / ".env", name))


def otkryt_klyuchi():
    return f'notepad "%USERPROFILE%\\.claude\\.env"' if WIN else "open -e ~/.claude/.env"


def kluch(name, gde=""):
    v = os.environ.get(name, "").strip() or _iz_faila(CLAUDE_ENV, name) or _iz_faila(ROOT / ".env", name)
    if not v:
        sys.exit(f"нет ключа {name}{': ' + gde if gde else ''}. Вставь его в файл ключей строкой {name}=… "
                 f"(Claude открывает файл командой `{otkryt_klyuchi()}`, сам ключ не читает).")
    return v


def dopisat_kluch(name, value):
    """Скрипт сам дописывает найденное значение (например, TELEGRAM_CHAT_ID). Ключ не печатается."""
    CLAUDE_ENV.parent.mkdir(parents=True, exist_ok=True)
    stroki = CLAUDE_ENV.read_text(encoding="utf-8-sig").splitlines() if CLAUDE_ENV.exists() else []
    stroki = [s for s in stroki if not s.startswith(name + "=")] + [f"{name}={value}"]
    CLAUDE_ENV.write_text("\n".join(stroki) + "\n", encoding="utf-8")


def venv_bin():
    return MONTAZH / ".venv" / ("Scripts" if WIN else "bin")


def programma(name):
    """Полный путь к ffmpeg / ffprobe / node / npm: сначала .venv монтажа, потом система."""
    p = shutil.which(name, path=str(venv_bin()) + os.pathsep + os.environ.get("PATH", ""))
    if not p:
        sys.exit(f"нет программы {name}: поставь монтаж (`install.py --chasti montazh`), он кладёт ffmpeg и Node в свою папку")
    return p


# дочерние процессы (curl, node, ffmpeg) тоже видят программы монтажа
if venv_bin().exists() and str(venv_bin()) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(venv_bin()) + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("PYTHONUTF8", "1")


def nastroika(pole, default=""):
    """Строка `- Поле: значение` из <завод>/local.md (запасное место — local.md в папке кода завода)."""
    for f in (zavod() / "local.md", ROOT / "local.md"):
        if f.exists():
            for line in f.read_text(encoding="utf-8-sig").splitlines():
                s = line.strip().lstrip("-").strip()
                if s.lower().startswith(pole.lower() + ":"):
                    v = s.split(":", 1)[1].strip()
                    if v and not v.startswith("("):
                        return v
    return default
