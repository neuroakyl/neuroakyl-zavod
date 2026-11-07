"""Установка контент-завода — Mac и Windows, без прав администратора. Запускает Claude Code (см. УСТАНОВКА.md).

  python3 install.py                               всё
  python3 install.py --chasti montazh,parser       только эти части: montazh, parser, karuseli
  python3 install.py --light                       монтаж без полных библиотек анимаций (~90 МБ вместо ~0,5 ГБ)

Завод — это правила и скрипты в этой папке плюс отдельные навыки: монтаж и парсер ставятся рядом, в папку навыков.
Повторный запуск безопасен: доставляет недостающее, обновляет git pull, ничего не удаляет.
"""
import argparse, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
SKILLS = ROOT.parent
REPOS = {"montazh": "https://github.com/neuroakyl/neuroakyl-montazh", "parser": "https://github.com/neuroakyl/instagram-parser"}
DIRS = {"montazh": "montazh", "parser": "instagram-parser"}

ap = argparse.ArgumentParser()
ap.add_argument("--chasti", default="montazh,parser,karuseli")
ap.add_argument("--light", action="store_true")
a = ap.parse_args()
want = [x.strip() for x in a.chasti.split(",") if x.strip()]
bad = []


def ok(m): print(f"  ✓ {m}", flush=True)
def err(m): print(f"  ✗ {m}", flush=True); bad.append(m)


print("1. Настройки")
for src, dst in ((".env.example", ".env"), ("local.example.md", "local.md")):
    if (ROOT / dst).exists():
        ok(f"{dst} уже есть, не трогаю")
    else:
        shutil.copy(ROOT / src, ROOT / dst)
        ok(f"{dst} создан")
if (ROOT / ".git").exists() and shutil.which("git"):
    subprocess.run(["git", "-C", str(ROOT), "config", "core.hooksPath", ".githooks"])

print("2. Части завода")
if not shutil.which("git") and (set(want) & set(REPOS)):
    sys.exit("нет git: Mac — `xcode-select --install`; Windows — `winget install --id Git.Git -e`. Потом запусти install.py ещё раз.")
for part in want:
    if part in REPOS:
        dst = SKILLS / DIRS[part]
        if dst.exists():
            r = subprocess.run(["git", "-C", str(dst), "pull", "--ff-only"], capture_output=True, text=True)
            ok(f"{part}: обновлён") if r.returncode == 0 else err(f"{part}: git pull не прошёл: {r.stderr.strip()[:200]}")
        else:
            r = subprocess.run(["git", "clone", "--depth", "1", REPOS[part], str(dst)], capture_output=True, text=True)
            ok(f"{part}: скачан в {dst}") if r.returncode == 0 else err(f"{part}: не скачался: {r.stderr.strip()[:200]}")
    elif part == "karuseli":
        ok("карусели: нужен только Node, пакет playwright ставится при первом запуске (модули/карусели.md)")
    else:
        err(f"нет такой части: {part}")

if "montazh" in want and (SKILLS / "montazh" / "install.py").exists():
    print("3. Монтаж: программы и пакеты (5–20 минут, один раз)")
    cmd = [sys.executable, "install.py"] + (["--light"] if a.light else [])
    if subprocess.run(cmd, cwd=SKILLS / "montazh").returncode:
        err("монтаж: установщик упал, смотри строки с ✗ выше")

print()
if bad:
    print("Есть ошибки:")
    for b in bad:
        print(" -", b)
    sys.exit(1)
print("Готово: части завода на месте. Дальше — УСТАНОВКА.md, шаг 2.")
