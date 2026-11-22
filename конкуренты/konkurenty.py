"""Конкуренты ниши: найти, собрать рилсы, найти залёты. Apify, только стандартная библиотека. Mac и Windows.

  py konkurenty.py poisk "запрос1, запрос2" [--skolko 20] [--da USD] [--fake]   аккаунты по словам ниши → кандидаты.json
  py konkurenty.py otbor                                                       кандидаты коротко + флаги «магазин? клиент?» → Claude пишет отбор.json
  py konkurenty.py otbor --proverit | --utverdit "ответ человека дословно"     проверить отбор.json | записать «да» человека
  py konkurenty.py sbor nik1 nik2 … [--rilsov 30] [--da USD] [--fake] [--svoi] рилсы каждого → <ник>/reels.json
  py konkurenty.py reiting                                                     рейтинг аккаунтов и залётов → рейтинг-ГГГГ-ММ-ДД.md
  py konkurenty.py smeta poisk|sbor …                                          сколько стоит, ничего не тратит

Папка: <завод>/конкуренты (Projects/завод/конкуренты). Ключ APIFY_TOKEN — из ~/.claude/.env.
Деньги: без --da запуска нет; --da меньше сметы — отказ; Apify сам останавливает актор на этой сумме (maxTotalChargeUsd).
Бесплатный план Apify — $5 в месяц: 10 аккаунтов × 30 рилсов ≈ $0,8. Обрыв сети: id запуска пишется сразу, повтор ждёт его, а не платит снова.
Конкурент = продаёт то же самое той же аудитории. Клиент, магазин, поставщик, СМИ, сосед по аудитории — не конкурент.
sbor берёт только ники из отбор.json с "to_zhe": true после --utverdit (или --svoi: ники назвал сам человек) — это в коде, не в обещаниях.
<ник>/reels.json — тот же формат, что у навыка instagram-parser: расшифровка залётов — его `insta.py звук` и `insta.py текст`.
"""
import argparse, datetime, json, pathlib, random, re, statistics, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z

PAPKA = Z.zavod() / "конкуренты"
API = "https://api.apify.com/v2"
# цена за 1000 результатов на бесплатном плане (apify.com, проверено 15.11.2026); с запасом, настоящий расход считает Apify
AKTORY = {"poisk": ("apify~instagram-scraper", 2.70), "sbor": ("apify~instagram-reel-scraper", 2.60)}
MIN_USD = 0.05  # у актора есть плата за старт, на копейки не запускаем


def http(url, data=None, timeout=90, popytok=4):
    head = {"Authorization": "Bearer " + Z.kluch("APIFY_TOKEN", "console.apify.com → Settings → API & Integrations"),
            "Content-Type": "application/json"}
    for i in range(popytok):  # слабый интернет: повторяем с паузой
        try:
            req = urllib.request.Request(url, json.dumps(data).encode() if data is not None else None, head)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            sys.exit(f"Apify ответил {e.code}: {e.read().decode(errors='replace')[:300]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == popytok - 1:
                sys.exit(f"нет связи с Apify ({e}). Запусти ту же команду ещё раз — начатый запуск подхватится.")
            time.sleep(5 * (i + 1))


def smeta(vid, n):
    return round(max(MIN_USD, n * AKTORY[vid][1] / 1000), 2)


def proverit_dengi(vid, n, a):
    s = smeta(vid, n)
    if a.fake:
        return s
    if a.da is None:
        sys.exit(f"смета: {n} результатов ≈ ${s}. Запуск только с --da {s} (или больше) после «да» человека.")
    if a.da < s:
        sys.exit(f"--da {a.da} меньше сметы ${s}: уменьши --skolko/--rilsov или подними потолок после «да» человека.")
    return a.da


def zapusk(vid, vhod, potolok, metka):
    """Запуск актора с потолком денег; id запуска хранится, повтор после обрыва ждёт его."""
    PAPKA.mkdir(parents=True, exist_ok=True)
    sost_f = PAPKA / ".zapuski.json"
    sost = json.loads(sost_f.read_text(encoding="utf-8")) if sost_f.exists() else {}
    run_id = sost.get(metka)
    if not run_id:
        q = urllib.parse.urlencode({"maxTotalChargeUsd": potolok})
        run = http(f"{API}/acts/{AKTORY[vid][0]}/runs?{q}", vhod)["data"]
        run_id = sost[metka] = run["id"]
        sost_f.write_text(json.dumps(sost, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  запущено ({metka}), жду…", flush=True)
    while True:
        run = http(f"{API}/actor-runs/{run_id}?waitForFinish=60")["data"]
        if run["status"] not in ("READY", "RUNNING"):
            break
    sost.pop(metka, None)
    sost_f.write_text(json.dumps(sost, ensure_ascii=False, indent=1), encoding="utf-8")
    if run["status"] != "SUCCEEDED":
        sys.exit(f"запуск {metka}: {run['status']} (за упавшее Apify берёт только за сделанное)")
    items = http(f"{API}/datasets/{run['defaultDatasetId']}/items?clean=true&format=json", timeout=300)
    usd = (run.get("usageTotalUsd") or 0)
    print(f"  ✓ {metka}: {len(items)} результатов, потрачено ≈ ${usd:.2f}", flush=True)
    with (PAPKA / "rashod.log").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%F %T')}\t{metka}\t{len(items)}\t${usd:.3f}\n")
    return items


# ---------- заглушки: весь путь без денег и без ключа ----------
def fake_profili(zaprosy, n):
    rnd = random.Random(1)
    return [{"username": f"proba_{i:02d}", "fullName": f"Проба {i}", "followersCount": rnd.choice([800, 5000, 40000, 250000]) * (i % 3 + 1),
             "postsCount": rnd.randint(40, 900), "biography": f"ниша: {zaprosy[i % len(zaprosy)]}" + (" · опт и доставка" if i % 7 == 3 else ""),
             "businessCategoryName": ["Стоматолог", "Магазин", "Блогер"][i % 3], "private": False, "verified": False}
            for i in range(n)]


def fake_rilsy(nik, n):
    rnd = random.Random(nik)
    base = rnd.choice([2000, 15000, 80000])
    now = datetime.datetime(2026, 11, 15)
    out = []
    for i in range(n):
        v = int(base * rnd.lognormvariate(0, 0.9))
        out.append({"ownerUsername": nik, "shortCode": f"{nik}{i:03d}", "url": f"https://www.instagram.com/reel/{nik}{i:03d}/",
                    "caption": f"Проба ролика {i}: хук про нишу", "videoViewCount": v, "videoPlayCount": v * 2,
                    "likesCount": v // 25, "commentsCount": v // 400, "videoDuration": rnd.randint(12, 70),
                    "timestamp": (now - datetime.timedelta(days=i * 2)).isoformat() + "Z"})
    return out


# ---------- команды ----------
def poisk(a):
    zaprosy = [z.strip() for z in " ".join(a.chto).split(",") if z.strip()]
    if not zaprosy:
        sys.exit('нужны слова ниши: poisk "фитнес для мам, похудение после родов"')
    n = a.skolko * len(zaprosy)
    potolok = proverit_dengi("poisk", n, a)
    vse = {}
    for z in zaprosy:
        items = fake_profili(zaprosy, a.skolko) if a.fake else zapusk(
            "poisk", {"search": z, "searchType": "user", "searchLimit": a.skolko, "resultsType": "details"},
            round(potolok / len(zaprosy), 2), f"poisk:{z}")
        for p in items:
            if p.get("username") and not p.get("private"):
                p["_zapros"] = z
                vse.setdefault(p["username"], p)
    PAPKA.mkdir(parents=True, exist_ok=True)
    (PAPKA / "кандидаты.json").write_text(json.dumps(list(vse.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"кандидатов: {len(vse)} → {PAPKA / 'кандидаты.json'}")
    for p in sorted(vse.values(), key=lambda p: -(p.get("followersCount") or 0))[:40]:
        print(f"  @{p['username']:<28} {p.get('followersCount') or 0:>9} подп.  {(p.get('businessCategoryName') or '')[:18]:<18} "
              f"{(p.get('biography') or '').replace(chr(10), ' ')[:60]}")
    print("Дальше: otbor — у каждого проверить «продаёт то же, что человек, той же аудитории?», клиентов и магазины выкинуть.")


# ---------- отбор: конкурент или нет ----------
OTBOR = PAPKA / "отбор.json"
KRUGI = ("прямой", "контент", "мир")
# слова, при которых кандидат чаще всего НЕ конкурент: магазин, поставщик, СМИ, работа, обучение для профи. Решает Claude, это подсказка.
FLAGI = {"магазин?": r"магазин|shop|store|опт\b|оптом|доставк|товар|склад|маркетплейс|wildberries|ozon|прайс|в наличии|дүкөн",
         "поставщик?": r"поставщик|оборудован|материал|расходник|запчаст|производств|завод\b|дистрибьют",
         "СМИ/афиша?": r"новост|news|афиша|журнал|медиа|подслушано|типичн|паблик|мемы",
         "работа?": r"ваканси|работа в|ищем|требуется|hr\b|рекрут",
         "клиент?": r"мама|мамочк|lifestyle|лайфстайл|влог|vlog|мой путь|мой опыт|мой отзыв|покупатель|пациент",
         "для профи?": r"для врачей|для мастеров|для стоматологов|для специалистов|повышени[ея] квалиф|b2b|для бизнеса|франшиз"}


def flagi(p):
    t = " ".join(str(p.get(k) or "") for k in ("biography", "businessCategoryName", "fullName", "username")).lower()
    return [f for f, rx in FLAGI.items() if re.search(rx, t)]


def otbor_chitat():
    if not OTBOR.exists():
        return None
    try:
        return json.loads(OTBOR.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"отбор.json сломан: {e}")


def otbor_oshibki(o):
    osh = []
    for pole in ("chto_prodaet", "komu"):
        if not (o.get(pole) or "").strip():
            osh.append(f"нет поля {pole}: что продаёт человек и кому — из мозга (продукт.md, аудитория.md)")
    akk = o.get("akkaunty") or []
    da = [x for x in akk if x.get("to_zhe") is True]
    for x in akk:
        n = x.get("nik", "?")
        if x.get("krug") not in KRUGI:
            osh.append(f"@{n}: krug должен быть одним из {', '.join(KRUGI)}")
        if not (x.get("prodaet") or "").strip():
            osh.append(f"@{n}: пусто prodaet — что этот аккаунт продаёт, по шапке и постам")
        if not (x.get("pochemu") or "").strip():
            osh.append(f"@{n}: пусто pochemu — почему он конкурент (или почему нет)")
        if x.get("to_zhe") is not True:
            osh.append(f"@{n}: to_zhe не true — не конкурент, перенеси в vybrosheno")
    if not 5 <= len(da) <= 12:
        osh.append(f"конкурентов {len(da)}: нужно 8–10 (от 5 в маленькой нише, до 12). Лишних — в zapas")
    if not any(x.get("krug") == "прямой" for x in da) and not (o.get("pryamyh_net") or "").strip():
        osh.append("нет ни одного прямого конкурента (то же самое там, где человек продаёт). Правда нет — "
                   "поле pryamyh_net с причиной, не натягивай чужого")
    return osh


def otbor(a):
    o = otbor_chitat()
    if a.proverit or a.utverdit is not None:
        if o is None:
            sys.exit(f"нет {OTBOR}: сначала напиши его (формат — модули/конкуренты.md, шаг 4)")
        osh = otbor_oshibki(o)
        if osh:
            print("✗ отбор не готов:")
            for x in osh:
                print("  -", x)
            sys.exit(1)
        if a.utverdit is not None:
            otvet = (a.utverdit or "").strip()
            if len(otvet) < 2 or otvet.startswith("-"):
                sys.exit('нужен ответ человека дословно: otbor --utverdit "да, собирай". Без его ответа в чате не запускай.')
            o["utverzhdeno"] = datetime.date.today().isoformat()
            o["otvet_cheloveka"] = otvet
            OTBOR.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"✓ отбор утверждён человеком ({o['utverzhdeno']}): sbor возьмёт эти ники")
        else:
            print("✓ отбор в порядке. Покажи человеку таблицу (ник · круг · что продаёт · почему) → после «да»: otbor --utverdit")
        return
    f = PAPKA / "кандидаты.json"
    if not f.exists():
        sys.exit("нет кандидаты.json: poisk, или впиши найденных бесплатно в кандидаты.json (формат — модули/конкуренты.md, шаг 3)")
    kand = json.loads(f.read_text(encoding="utf-8"))
    print(f"{len(kand)} кандидатов. У каждого ответь: продаёт то же, что человек, той же аудитории? Нет — в vybrosheno с причиной.")
    for p in sorted(kand, key=lambda p: -(p.get("followersCount") or 0)):
        fl = flagi(p)
        print(f"@{p['username']} · {p.get('followersCount') or 0} подп. · {p.get('businessCategoryName') or '—'} · "
              f"запрос «{p.get('_zapros', '')}»{' · ⚠ ' + ' '.join(fl) if fl else ''}\n    "
              f"{(p.get('biography') or '').replace(chr(10), ' ')[:150]}  {p.get('externalUrl') or ''}")
    print(f"\nДальше: напиши {OTBOR} → otbor --proverit")


def sbor(a):
    niki = [n.strip().lstrip("@").rstrip("/").split("/")[-1] for n in a.chto if n.strip()]
    if not niki:
        sys.exit("нужны ники: sbor nik1 nik2 …")
    if not a.svoi:  # деньги только на проверенных конкурентов (и заглушка тоже: мусор не должен попасть в рейтинг)
        o = otbor_chitat()
        if not o or not o.get("utverzhdeno"):
            sys.exit("сначала отбор: otbor → отбор.json → otbor --proverit → «да» человека → otbor --utverdit. "
                     "Ники назвал сам человек — добавь --svoi.")
        ok_niki = {x["nik"].lstrip("@").lower() for x in o.get("akkaunty", []) if x.get("to_zhe") is True}
        chuzhie = [n for n in niki if n.lower() not in ok_niki]
        if chuzhie:
            sys.exit(f"не в утверждённом отборе: {', '.join(chuzhie)}. Это точно конкуренты? Добавь в отбор.json и утверди заново.")
    potolok = proverit_dengi("sbor", len(niki) * a.rilsov, a)
    for nik in niki:
        out = PAPKA / nik
        f = out / "reels.json"
        if f.exists() and not a.zanovo:
            print(f"  = @{nik}: уже собран (--zanovo, чтобы обновить)")
            continue
        items = fake_rilsy(nik, a.rilsov) if a.fake else zapusk(
            "sbor", {"username": [nik], "resultsLimit": a.rilsov, "skipPinnedPosts": True},
            round(potolok / len(niki), 2), f"sbor:{nik}")
        out.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        if a.fake:
            print(f"  ~ @{nik}: {len(items)} рилсов (заглушка)")
    print("Дальше: reiting")


def prosmotry(r):
    return r.get("videoPlayCount") or r.get("videoViewCount") or 0


def reiting(a):
    kand = {p["username"]: p for p in json.loads((PAPKA / "кандидаты.json").read_text(encoding="utf-8"))} \
        if (PAPKA / "кандидаты.json").exists() else {}
    akk, zalety = [], []
    for f in sorted(PAPKA.glob("*/reels.json")):
        rs = [r for r in json.loads(f.read_text(encoding="utf-8")) if prosmotry(r)]
        if not rs:
            continue
        nik = f.parent.name
        med = statistics.median(prosmotry(r) for r in rs)
        dni = sorted(r["timestamp"][:10] for r in rs if r.get("timestamp"))
        span = max(1, (datetime.date.fromisoformat(dni[-1]) - datetime.date.fromisoformat(dni[0])).days) if len(dni) > 1 else 7
        er = statistics.median(((r.get("likesCount") or 0) + (r.get("commentsCount") or 0)) / prosmotry(r) for r in rs)
        akk.append({"nik": nik, "podp": (kand.get(nik) or {}).get("followersCount"), "rilsov": len(rs), "med": int(med),
                    "v_nedelyu": round(len(rs) / span * 7, 1), "er": er, "posl": dni[-1] if dni else ""})
        for r in rs:
            x = prosmotry(r) / med if med else 0
            zalety.append({"nik": nik, "x": x, "v": prosmotry(r), "url": r.get("url", ""), "dlit": r.get("videoDuration"),
                           "kom": r.get("commentsCount") or 0, "tekst": (r.get("caption") or "").replace("\n", " ")[:90],
                           "kod": r.get("shortCode")})
    if not akk:
        sys.exit("нечего считать: сначала sbor")
    akk.sort(key=lambda x: -x["med"])
    top = sorted((z for z in zalety if z["x"] >= 2), key=lambda z: (-z["x"], -z["v"]))[:30]
    d = datetime.date.today().isoformat()
    s = [f"# Конкуренты: рейтинг {d}", "", "Залёт — рилс, набравший в 2+ раза больше медианы своего аккаунта: тема и хук доказаны у этой аудитории.",
         "", "## Аккаунты (по медиане просмотров)", "| Аккаунт | Подписчики | Рилсов | Медиана | В неделю | Вовлечённость | Последний рилс |", "|---|---|---|---|---|---|---|"]
    mert = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    s += [f"| @{x['nik']} | {x['podp'] or '—'} | {x['rilsov']} | {x['med']} | {x['v_nedelyu']} | {x['er'] * 100:.1f}% | "
          f"{x['posl']}{' ⚠ не живой: в разбор не брать' if x['posl'] and x['posl'] < mert else ''} |" for x in akk]
    s += ["", "## Залёты (×медиана)", "| × | Просмотры | Коммент. | Сек | Аккаунт | Подпись | Ссылка |", "|---|---|---|---|---|---|---|"]
    s += [f"| {z['x']:.1f} | {z['v']} | {z['kom']} | {z['dlit'] or '—'} | @{z['nik']} | {z['tekst'].replace('|', '/')} | {z['url']} |" for z in top]
    s += ["", "## Что дальше (делает Claude, модуль `конкуренты.md`)",
          "1. Расшифровать топ-залёты: навык instagram-parser, `insta.py звук <папка ника>` и `insta.py текст <папка ника>`.",
          "2. Разобрать: тип темы, хук первых 2 секунд, формат, длина, призыв → `разбор-ГГГГ-ММ-ДД.md` и `мозг/доноры.md`.",
          "3. Контент-план «широко → узко» — модуль `контент-план.md`."]
    out = PAPKA / f"рейтинг-{d}.md"
    out.write_text("\n".join(s) + "\n", encoding="utf-8")
    print(f"аккаунтов {len(akk)}, залётов {len(top)} → {out}")


def smeta_cmd(a):
    vid = (a.chto or [""])[0]
    if vid == "poisk":
        n = a.skolko * max(1, len([z for z in " ".join(a.chto[1:]).split(",") if z.strip()]))
    elif vid == "sbor":
        n = max(1, len(a.chto) - 1) * a.rilsov
    else:
        sys.exit("smeta poisk \"запросы\" | smeta sbor nik1 nik2 …")
    print(f"{vid}: {n} результатов ≈ ${smeta(vid, n)} (бесплатно Apify даёт $5 в месяц)")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("cmd", choices=["poisk", "otbor", "sbor", "reiting", "smeta"])
ap.add_argument("chto", nargs="*")
ap.add_argument("--skolko", type=int, default=20)
ap.add_argument("--rilsov", type=int, default=30)
ap.add_argument("--da", type=float)
ap.add_argument("--fake", action="store_true")
ap.add_argument("--zanovo", action="store_true")
ap.add_argument("--svoi", action="store_true")
ap.add_argument("--proverit", action="store_true")
ap.add_argument("--utverdit", nargs="?", const="", default=None)
A = ap.parse_args()
{"poisk": poisk, "otbor": otbor, "sbor": sbor, "reiting": reiting, "smeta": smeta_cmd}[A.cmd](A)
