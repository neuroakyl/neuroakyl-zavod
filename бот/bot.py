"""Telegram-бот завода: пульт с телефона на официальном канале Claude Code (плагин telegram@claude-plugins-official).
Mac и Windows. Порядок — модули/бот.md. Токен бота читается из ~/.claude/.env (TELEGRAM_BOT_TOKEN), в чат не попадает.

  py bot.py proverka      что есть: Claude Code в терминале, Bun, плагин, токен, свой chat id
  py bot.py nastroit      токен → канал Claude Code; ждёт, пока человек нажмёт Start у бота; запоминает его chat id;
                          тестовое сообщение; плагин выключен для всех чатов и включается только в окне бота
  py bot.py avtozapusk    окно бота открывается само при входе в компьютер (Windows — папка «Автозагрузка», Mac — объекты входа)
  py bot.py zapusk        открыть окно бота сейчас (в нём работает Claude, окно не закрывать)
"""
import json, os, pathlib, shutil, subprocess, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z

PLAGIN = "telegram@claude-plugins-official"
CLAUDE = Z.HOME / ".claude"
KANAL_ENV = CLAUDE / "channels" / "telegram" / ".env"
BOT_SETTINGS = CLAUDE / "zavod-bot.json"           # включает плагин только в окне бота
ZAPUSK = Z.proekty() / ("zavod-bot.cmd" if Z.WIN else "zavod-bot.command")


def tg(method, data=None, timeout=40):
    t = Z.kluch("TELEGRAM_BOT_TOKEN", "Telegram → @BotFather → /newbot")
    req = urllib.request.Request(f"https://api.telegram.org/bot{t}/{method}", json.dumps(data or {}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def claude_cli():
    return shutil.which("claude") or next((str(p) for p in (Z.HOME / ".local" / "bin" / ("claude.exe" if Z.WIN else "claude"),)
                                           if p.exists()), None)


def bun():
    return shutil.which("bun") or next((str(p) for p in (Z.HOME / ".bun" / "bin" / ("bun.exe" if Z.WIN else "bun"),) if p.exists()), None)


def proverka():
    vse = True
    def stroka(est, chto, kak):
        nonlocal vse
        print(f"✓ {chto}" if est else f"✗ {chto}\n    как: {kak}")
        vse = vse and bool(est)
    stroka(claude_cli(), "Claude Code в терминале (команда claude)",
           "Windows: powershell -c \"irm https://claude.ai/install.ps1 | iex\"; Mac: curl -fsSL https://claude.ai/install.sh | bash")
    stroka(bun(), "Bun (на нём работает канал Telegram)",
           "Windows: powershell -c \"irm bun.sh/install.ps1 | iex\"; Mac: curl -fsSL https://bun.sh/install | bash")
    pl = subprocess.run([claude_cli(), "plugin", "list"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout \
        if claude_cli() else ""
    stroka("telegram" in pl, "плагин Telegram установлен", f"claude plugin install {PLAGIN}")
    stroka(Z.est_kluch("TELEGRAM_BOT_TOKEN"), "токен бота в ~/.claude/.env", "@BotFather → /newbot → токен в файл ключей")
    stroka(Z.est_kluch("TELEGRAM_CHAT_ID"), "бот знает тебя (chat id)", "py bot.py nastroit")
    stroka(KANAL_ENV.exists() and BOT_SETTINGS.exists(), "канал настроен", "py bot.py nastroit")
    print("\nБОТ ГОТОВ К ЗАПУСКУ" if vse else "\nЕСТЬ ЧТО ПОСТАВИТЬ")
    return vse


def nastroit():
    me = tg("getMe")
    if not me.get("ok"):
        sys.exit("токен не подошёл: проверь, что вставлен целиком (@BotFather → /mybots → API Token)")
    nik = me["result"]["username"]
    if not Z.est_kluch("TELEGRAM_CHAT_ID"):
        print(f"Открой в Telegram @{nik} и нажми «Старт» (или напиши ему что угодно). Жду до 3 минут…", flush=True)
        cid, konec = None, time.time() + 180
        while not cid and time.time() < konec:
            ups = tg("getUpdates", {"timeout": 25}).get("result", [])
            chats = [u["message"]["chat"]["id"] for u in ups if "message" in u and u["message"]["chat"]["type"] == "private"]
            cid = chats[-1] if chats else None
        if not cid:
            sys.exit("не дождался сообщения боту — запусти nastroit ещё раз и нажми Start")
        Z.dopisat_kluch("TELEGRAM_CHAT_ID", cid)
    # токен — каналу Claude Code (то же делает команда /telegram:configure), без вывода в чат
    novoe = f"TELEGRAM_BOT_TOKEN={Z.kluch('TELEGRAM_BOT_TOKEN')}\n"
    if KANAL_ENV.exists() and KANAL_ENV.read_text(encoding="utf-8").strip() != novoe.strip() and "--zamenit" not in sys.argv:
        sys.exit("у Claude Code уже настроен другой Telegram-бот. Заменить его этим — только по слову человека: nastroit --zamenit")
    KANAL_ENV.parent.mkdir(parents=True, exist_ok=True)
    KANAL_ENV.write_text(novoe, encoding="utf-8")
    # плагин: для всех чатов выключен (иначе каждый новый чат перехватывает бота), в окне бота — включён
    BOT_SETTINGS.write_text(json.dumps({"enabledPlugins": {PLAGIN: True}}, indent=2) + "\n", encoding="utf-8")
    sf = CLAUDE / "settings.json"
    s = json.loads(sf.read_text(encoding="utf-8-sig")) if sf.exists() else {}
    s.setdefault("enabledPlugins", {})[PLAGIN] = False
    sf.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # ярлык запуска в папке Projects
    if Z.WIN:
        pr = str(Z.proekty()) if str(Z.proekty()).isascii() else "%USERPROFILE%\\Projects"  # .cmd не любит кириллицу
        ZAPUSK.write_text(f"@echo off\r\ntitle Zavod bot - ne zakryvat\r\ncd /d \"{pr}\"\r\n"
                          f"claude --settings \"%USERPROFILE%\\.claude\\zavod-bot.json\" --channels plugin:{PLAGIN}\r\n",
                          encoding="ascii")
    else:
        ZAPUSK.write_text("#!/bin/bash\n# Окно бота завода: не закрывать, можно свернуть\n"
                          f"cd \"{Z.proekty()}\"\nexec claude --settings \"$HOME/.claude/zavod-bot.json\" --channels plugin:{PLAGIN}\n",
                          encoding="utf-8")
        ZAPUSK.chmod(0o755)
    cid = os.environ.get("TELEGRAM_CHAT_ID") or Z._iz_faila(Z.CLAUDE_ENV, "TELEGRAM_CHAT_ID")
    tg("sendMessage", {"chat_id": cid, "text": "Завод на связи. Скоро здесь будет Claude: присылай задачи, сюда придут ролики и кнопки разрешений."})
    print(f"✓ бот @{nik} настроен, тестовое сообщение отправлено\n✓ ярлык запуска: {ZAPUSK}\n"
          "Дальше: `bot.py zapusk`, в окне бота один раз пройти привязку (модули/бот.md, шаг 5)")


def zapusk():
    if not ZAPUSK.exists():
        sys.exit("сначала bot.py nastroit")
    if Z.WIN:
        subprocess.Popen(["cmd", "/c", "start", "Zavod bot", "cmd", "/k", str(ZAPUSK)])
    else:
        subprocess.run(["open", "-a", "Terminal", str(ZAPUSK)])
    print("окно бота открыто: в нём работает Claude, не закрывай (можно свернуть)")


def avtozapusk():
    if not ZAPUSK.exists():
        sys.exit("сначала bot.py nastroit")
    if Z.WIN:
        start = pathlib.Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "zavod-bot.cmd"
        start.write_text(f"@echo off\r\nstart \"Zavod bot\" /min cmd /k \"{ZAPUSK}\"\r\n", encoding="ascii")
        print(f"✓ автозапуск: {start}")
    else:
        r = subprocess.run(["osascript", "-e", f'tell application "System Events" to make login item at end with properties '
                            f'{{path:"{ZAPUSK}", hidden:true}}'], capture_output=True, text=True)
        print("✓ автозапуск: объекты входа macOS" if r.returncode == 0 else
              f"не вышло ({r.stderr.strip()[:200]}): Системные настройки → Основные → Объекты входа → + → {ZAPUSK}")
    print("Компьютер не должен засыпать, пока бот нужен: Mac — Настройки → Аккумулятор → не засыпать от сети; "
          "Windows — Параметры → Система → Питание → Никогда (от сети).")


cmd = (sys.argv[1:] or ["proverka"])[0]
{"proverka": proverka, "nastroit": nastroit, "zapusk": zapusk, "avtozapusk": avtozapusk}.get(cmd, lambda: sys.exit(__doc__))()
