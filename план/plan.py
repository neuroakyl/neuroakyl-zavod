"""Контент-план как очередь: Claude пишет план, человек говорит «да», дальше Claude сам берёт следующие пункты и выпускает пачкой.
Только стандартная библиотека, Mac и Windows.

  py plan.py proverit [--plan F]                       проверить план: поля, номера, даты, хуки, повторы
  py plan.py pokazat  [--plan F]                       план-ГГГГ-ММ.md — таблица для человека (генерируется сама после da/otmetit/sdvig)
  py plan.py da       [--plan F]                       записать «да» человека: все пункты встают в очередь
  py plan.py dalshe   [--format reels] [--n 10]        следующие пункты очереди (по дате выхода) — что выпускать сейчас
  py plan.py otmetit ID status [--papka P] [--fail F] [--ssylka URL] [--kogda "ГГГГ-ММ-ДД ЧЧ:ММ"]
  py plan.py sdvig N [--format reels]                  сдвинуть даты всего невышедшего на N дней (пропустили дни)
  py plan.py status                                    сколько чего на каком шаге и что дальше

План: Projects/завод/планы/план-ГГГГ-ММ.json (берётся самый новый). Форматы: reels, karusel, threads, storis.
Статусы: plan → v-ocheredi (после «da») → scenariy → gotov → zaplanirovan → vyshel; snyat — убран из плана.
«dalshe» без «да» человека ничего не выдаёт: это в коде, не в обещаниях. Вышедшее пишется строкой в мозг/снятое.md.
"""
import argparse, datetime, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import zavod_obshchee as Z

PLANY = Z.zavod() / "планы"
FORMATY = {"reels": "R", "karusel": "K", "threads": "T", "storis": "S"}
IMYA = {"reels": "Reels", "karusel": "Карусель", "threads": "Threads", "storis": "Сторис"}
CELI = ("охват", "доверие", "продажа", "сообщество")
STATUSY = ("plan", "v-ocheredi", "scenariy", "gotov", "zaplanirovan", "vyshel", "snyat")
NE_VYSHLO = ("v-ocheredi", "scenariy", "gotov")
NADO = {  # обязательные поля по формату
    "reels": ("data", "cel", "tema", "huk", "yazyk", "prizyv"),
    "karusel": ("data", "cel", "tema", "huk", "yazyk", "prizyv"),
    "threads": ("data", "cel", "tekst", "yazyk"),
    "storis": ("data", "cel", "tema"),
}


def plan_fail(a):
    if a.plan:
        return pathlib.Path(a.plan)
    vse = sorted(PLANY.glob("план-*.json"))
    if not vse:
        sys.exit(f"плана нет: напиши {PLANY / 'план-ГГГГ-ММ.json'} по модули/контент-план.md")
    return vse[-1]


def chitat(f):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{f.name} сломан: {e}")


def pisat(f, p):
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def slov(t):
    return len(re.findall(r"\w+", t or ""))


def oshibki(p):
    osh, preduprezhdeniya, ids, temy = [], [], set(), {}
    ed = p.get("edinicy") or []
    if not re.fullmatch(r"\d{4}-\d{2}", p.get("mesyac") or ""):
        osh.append("поле mesyac — ГГГГ-ММ")
    if not ed:
        osh.append("в плане нет edinicy")
    for e in ed:
        i, fmt = e.get("id", "?"), e.get("format")
        if fmt not in FORMATY:
            osh.append(f"{i}: format — один из {', '.join(FORMATY)}")
            continue
        if not re.fullmatch(FORMATY[fmt] + r"\d{2,3}", str(i)):
            osh.append(f"{i}: номер формата {fmt} — {FORMATY[fmt]}01, {FORMATY[fmt]}02 …")
        if i in ids:
            osh.append(f"{i}: номер повторяется")
        ids.add(i)
        for pole in NADO[fmt]:
            if not str(e.get(pole) or "").strip():
                osh.append(f"{i}: пусто поле {pole}")
        try:
            datetime.date.fromisoformat(e.get("data", ""))
        except ValueError:
            osh.append(f"{i}: data — ГГГГ-ММ-ДД")
        if e.get("cel") and e["cel"] not in CELI:
            osh.append(f"{i}: cel — одна из {', '.join(CELI)}")
        if e.get("yazyk") and e["yazyk"] not in ("ky", "ru", "ky+ru", "en", "kk", "uz"):
            osh.append(f"{i}: yazyk — ky, ru, ky+ru (или en, kk, uz)")
        if e.get("status", "plan") not in STATUSY:
            osh.append(f"{i}: status — один из {', '.join(STATUSY)}")
        if fmt in ("reels", "karusel"):
            n = slov(e.get("huk"))
            if n > 14:
                preduprezhdeniya.append(f"{i}: хук {n} слов — для первых 2 секунд длинно (до 12–14)")
            if len(e.get("huk_zapas") or []) < 2 and fmt == "reels":
                preduprezhdeniya.append(f"{i}: нет двух запасных хуков (huk_zapas) — пробные рилсы с разным началом")
            k = re.sub(r"\W+", " ", (e.get("tema") or "").lower()).strip()
            if k and k in temy:
                osh.append(f"{i}: та же тема, что {temy[k]}")
            temy[k] = i
        if fmt == "threads" and len(e.get("tekst") or "") > 500:
            osh.append(f"{i}: Threads до 500 знаков")
    return osh, preduprezhdeniya


def proverit(a):
    f = plan_fail(a)
    p = chitat(f)
    osh, pr = oshibki(p)
    for x in pr:
        print("  ! " + x)
    if osh:
        print(f"✗ {f.name}: исправь")
        for x in osh:
            print("  - " + x)
        sys.exit(1)
    sch = {}
    for e in p["edinicy"]:
        sch[e["format"]] = sch.get(e["format"], 0) + 1
    print(f"✓ {f.name}: " + ", ".join(f"{IMYA[k]} {v}" for k, v in sch.items()))


def pokazat(a):
    f = plan_fail(a)
    p = chitat(f)
    ed = sorted((e for e in p.get("edinicy", []) if e.get("status") != "snyat"), key=lambda e: (e.get("data", ""), e.get("id", "")))
    s = [f"# Контент-план {p.get('mesyac')}", "",
         "_Генерируется из " + f.name + " командой `plan.py pokazat`. Правки — в JSON, потом снова pokazat._", ""]
    if p.get("utverzhden"):
        s.append(f"Утверждён: {p['utverzhden']}. Claude выпускает по очереди сам.")
    else:
        s.append("**Ждёт «да».** Ответь «да» или номерами: «R04 — замени», «T10 убрать».")
    for pole, imya in (("strategiya", "Стратегия"), ("razbor", "Разбор рынка"), ("norma", "Норма"), ("smeta", "Деньги на месяц")):
        if p.get(pole):
            v = p[pole]
            s.append(f"{imya}: " + (", ".join(f"{IMYA.get(k, k)} {x}" for k, x in v.items()) if isinstance(v, dict) else str(v)))
    nedeli = {}
    for e in ed:
        d = datetime.date.fromisoformat(e["data"])
        nedeli.setdefault(d.isocalendar()[1], []).append(e)
    for n, (_, gr) in enumerate(sorted(nedeli.items()), 1):
        s += ["", f"## Неделя {n}: {gr[0]['data']} — {gr[-1]['data']}", "",
              "| № | Дата | Формат | Цель | Тема | Хук / текст | Язык | Призыв | Статус |", "|---|---|---|---|---|---|---|---|---|"]
        for e in gr:
            t = (e.get("huk") or e.get("tekst") or e.get("chto") or "").replace("|", "/").replace("\n", " ")
            s.append(f"| {e['id']} | {e['data'][5:]} | {IMYA[e['format']]} | {e.get('cel', '')} | {(e.get('tema') or '').replace('|', '/')} | "
                     f"{t[:140]} | {e.get('yazyk', '')} | {(e.get('prizyv') or '').replace('|', '/')} | {e.get('status', 'plan')} |")
    out = f.with_suffix(".md")
    out.write_text("\n".join(s) + "\n", encoding="utf-8")
    print(f"→ {out}")


def da(a):
    f = plan_fail(a)
    p = chitat(f)
    osh, _ = oshibki(p)
    if osh:
        sys.exit("сначала proverit: в плане ошибки (" + "; ".join(osh[:3]) + ")")
    p["utverzhden"] = datetime.date.today().isoformat()
    n = 0
    for e in p["edinicy"]:
        if e.get("status", "plan") == "plan":
            e["status"] = "v-ocheredi"
            n += 1
    pisat(f, p)
    pokazat(a)
    print(f"✓ «да» записано {p['utverzhden']}: в очереди {n} пунктов. Дальше: dalshe --format reels --n 10")


def dalshe(a):
    f = plan_fail(a)
    p = chitat(f)
    if not p.get("utverzhden"):
        sys.exit("план не утверждён: покажи план человеку (pokazat), после его «да» — plan.py da")
    ed = [e for e in p["edinicy"] if e.get("status") in ("v-ocheredi", "scenariy") and (not a.format or e["format"] == a.format)]
    ed.sort(key=lambda e: (e.get("data", ""), e["id"]))
    if not ed:
        print("в очереди пусто" + (f" по формату {a.format}" if a.format else "") + ": пора новый план или разбор недели")
        return
    for e in ed[:a.n]:
        print(json.dumps(e, ensure_ascii=False))
    ost = len(ed) - min(a.n, len(ed))
    print(f"# выдано {min(a.n, len(ed))}, в очереди ещё {ost}. Каждый пункт: сценарий → готово → otmetit ID gotov --fail …")


def otmetit(a):
    f = plan_fail(a)
    p = chitat(f)
    if a.status not in STATUSY:
        sys.exit(f"статус — один из {', '.join(STATUSY)}")
    e = next((x for x in p.get("edinicy", []) if x.get("id") == a.id), None)
    if not e:
        sys.exit(f"нет пункта {a.id} в {f.name}")
    if a.status not in ("plan", "snyat") and not p.get("utverzhden"):
        sys.exit("план не утверждён человеком: plan.py da только после его «да»")
    if a.status == "vyshel" and not (a.ssylka or e.get("ssylka")):
        sys.exit("«вышел» только со ссылкой на пост: --ssylka URL")
    e["status"] = a.status
    for k in ("papka", "fail", "ssylka", "kogda"):
        if getattr(a, k):
            e[k] = getattr(a, k)
    pisat(f, p)
    if a.status == "vyshel":
        sn = Z.proekty() / "мозг" / "снятое.md"
        if sn.exists():
            with sn.open("a", encoding="utf-8") as g:
                g.write(f"\n- {datetime.date.today().isoformat()} · {IMYA[e['format']]} · {e.get('tema', '')} · "
                        f"«{e.get('huk') or (e.get('tekst') or '')[:60]}» · {e.get('cel', '')} · {e.get('mekhanika', '')} · "
                        f"цифры через 48 ч — (собрать) · {e.get('ssylka', '')}")
    pokazat(a)
    print(f"✓ {a.id}: {a.status}")


def sdvig(a):
    f = plan_fail(a)
    p = chitat(f)
    n = 0
    for e in p.get("edinicy", []):
        if e.get("status") in ("plan",) + NE_VYSHLO and (not a.format or e["format"] == a.format):
            e["data"] = (datetime.date.fromisoformat(e["data"]) + datetime.timedelta(days=a.dney)).isoformat()
            n += 1
    pisat(f, p)
    pokazat(a)
    print(f"✓ сдвинуто {n} пунктов на {a.dney} дн.")


def status(a):
    f = plan_fail(a)
    p = chitat(f)
    t = {}
    for e in p.get("edinicy", []):
        t.setdefault(e["format"], {}).setdefault(e.get("status", "plan"), 0)
        t[e["format"]][e.get("status", "plan")] += 1
    print(f"{f.name} · " + (f"утверждён {p['utverzhden']}" if p.get("utverzhden") else "ждёт «да»"))
    for fmt, st in t.items():
        print(f"  {IMYA[fmt]:<9} " + " · ".join(f"{k} {v}" for k, v in st.items()))
    segodnya = datetime.date.today().isoformat()
    prosrok = [e["id"] for e in p.get("edinicy", []) if e.get("status") in NE_VYSHLO and e.get("data", "9") < segodnya]
    if prosrok:
        print(f"  ! просрочено (дата прошла, не вышло): {', '.join(prosrok[:15])} — выпустить или sdvig")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
for c in ("proverit", "pokazat", "da", "status"):
    sub.add_parser(c).add_argument("--plan")
x = sub.add_parser("dalshe"); x.add_argument("--plan"); x.add_argument("--format", choices=list(FORMATY)); x.add_argument("--n", type=int, default=10)
x = sub.add_parser("otmetit"); x.add_argument("id"); x.add_argument("status"); x.add_argument("--plan")
for k in ("papka", "fail", "ssylka", "kogda"):
    x.add_argument("--" + k)
x = sub.add_parser("sdvig"); x.add_argument("dney", type=int); x.add_argument("--plan"); x.add_argument("--format", choices=list(FORMATY))
A = ap.parse_args()
{"proverit": proverit, "pokazat": pokazat, "da": da, "dalshe": dalshe, "otmetit": otmetit, "sdvig": sdvig, "status": status}[A.cmd](A)
