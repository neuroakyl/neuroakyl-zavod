#!/bin/bash
# Чистая установка завода на «новом ученике» (поддельный HOME) — Mac/Linux. Windows так не проверить: см. тест-windows.md.
# Запуск: bash test/chistaya-ustanovka.sh <пустая папка> <папка пакета umnyi-claude> <папка с копиями montazh и instagram-parser>
#   третий аргумент — локальные git-копии вместо GitHub (install.py --istochnik); без него качается с GitHub.
# Денег не тратит: генерации и Apify — заглушки (--fake). Сеть нужна для pip, Node и npm (кэши берутся с настоящего HOME).
set -u
ZAVOD="$(cd "$(dirname "$0")/.." && pwd)"
BAZA="${1:?пустая папка}"; UMNYI="${2:?папка пакета umnyi-claude}"; SRC="${3:-}"
mkdir -p "$BAZA"; BAZA="$(cd "$BAZA" && pwd)"
REAL_HOME="$HOME"
export PIP_CACHE_DIR="$REAL_HOME/Library/Caches/pip" npm_config_cache="$REAL_HOME/.npm"
export HOME="$BAZA/home"; mkdir -p "$HOME"
ok=0; fail=0
pass() { echo "✓ $1"; ok=$((ok+1)); }
nope() { echo "✗ $1"; fail=$((fail+1)); }
py() { sh "$HOME/.claude/umnyi/bin/py" "$@"; }

echo "== 1. Умный Claude"
git clone -q "$UMNYI" "$HOME/.claude/umnyi"
py "$HOME/.claude/umnyi/install.py" --tiho && pass "пакет поставлен" || nope "пакет"

echo "== 2. Завод (как git clone: только файлы репозитория)"
mkdir -p "$HOME/.claude/skills/zavod"
(cd "$ZAVOD" && git ls-files -co --exclude-standard -z | rsync -a --from0 --files-from=- ./ "$HOME/.claude/skills/zavod/")
Z="$HOME/.claude/skills/zavod"
ARGS=(--chasti montazh,parser,karuseli --bez-paka); [ -n "$SRC" ] && ARGS+=(--istochnik "$SRC")
py "$Z/install.py" "${ARGS[@]}" > "$BAZA/install.log" 2>&1 && pass "install.py завода" || { nope "install.py завода"; tail -30 "$BAZA/install.log"; }
py "$Z/install.py" --chasti parser > "$BAZA/install2.log" 2>&1 && pass "повторный install.py" || nope "повторный install.py"
[ -f "$HOME/Projects/завод/local.md" ] && [ -d "$HOME/Projects/завод/конкуренты" ] && pass "папка завода в Projects" || nope "папка завода"
[ ! -e "$Z/.env" ] && [ ! -e "$Z/local.md" ] && pass "в папке навыка нет ключей и настроек" || nope "данные в папке навыка"
grep -q '^APIFY_TOKEN=' "$HOME/.claude/.env" && grep -q '^ELEVENLABS_API_KEY=' "$HOME/.claude/.env" && pass "имена ключей в ~/.claude/.env" || nope "ключи"
[ "$(grep -c '^KIE_API_KEY=' "$HOME/.claude/.env")" = 1 ] && pass "ключи не задублированы" || nope "дубли ключей"

echo "== 3. Проверка с черновым роликом"
py "$Z/proverka.py" --render > "$BAZA/proverka.log" 2>&1; cat "$BAZA/proverka.log"
grep -q "ЗАВОД РАБОТАЕТ" "$BAZA/proverka.log" && pass "proverka --render" || nope "proverka --render"

echo "== 4. Ролик без лица на заглушках в рабочей папке ученика"
py "$Z/ролик/rolik.py" new "первый ролик" --tip bez-lica > /dev/null && R="$(ls -d "$HOME/Projects/завод/ролики/"*-первый-ролик | head -1)"
printf '# Первый ролик\n\n## Текст\nТри ошибки новичка в контенте. Первая: снимать без плана. Вторая: ждать идеала. Третья: бросить через неделю.\n' > "$R/сценарий.md"
py "$Z/ролик/rolik.py" zaglushka "$R" > "$BAZA/rolik.log" 2>&1 && [ -s "$R/черновик.mp4" ] && pass "черновик: $R/черновик.mp4" || { nope "черновик"; tail -20 "$BAZA/rolik.log"; }

echo "== 5. Креатив на заглушках → монтаж Klipy, горизонталь"
K="$HOME/Projects/завод/креатив/проба"
py "$Z/креатив/kreativ.py" new "$K" --format horizontal > /dev/null
py - "$K/proekt.json" <<'EOF'
import json, sys
f = sys.argv[1]; p = json.load(open(f, encoding="utf-8"))
p["svyazka"] = "deshevo"
p["geroi"][0].update(opisanie="пастух в калпаке", promt="kyrgyz shepherd, white kalpak")
p["kadry"] = [dict(p["kadry"][0], id="01", tekst="горы", promt="mountains at dawn", dlina=2),
              dict(p["kadry"][0], id="02", tekst="юрта", promt="yurt in valley", dlina=2, klip=False)]
json.dump(p, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
EOF
py "$Z/креатив/kreativ.py" geroi "$K" --fake > /dev/null && py "$Z/креатив/kreativ.py" kadry "$K" --fake > /dev/null \
  && py "$Z/креатив/kreativ.py" klipy "$K" --fake > /dev/null && pass "креатив --fake: герои, кадры, клипы" || nope "креатив --fake"
py "$Z/ролик/rolik.py" new "креатив проба" --tip kreativ --format horizontal > /dev/null
RK="$(ls -d "$HOME/Projects/завод/ролики/"*-креатив-проба | head -1)"
py "$Z/креатив/kreativ.py" sobrat "$K" --dvizhok "$RK/движок" > /dev/null && py "$Z/ролик/rolik.py" render "$RK" креатив > "$BAZA/kreativ.log" 2>&1 \
  && [ -s "$RK/креатив.mp4" ] && pass "креатив собран и отрендерен: $RK/креатив.mp4" || { nope "креатив → монтаж"; tail -20 "$BAZA/kreativ.log"; }

echo "== 6. Конкуренты на заглушках"
py "$Z/конкуренты/konkurenty.py" poisk "фитнес для мам" --fake --skolko 6 > /dev/null \
  && py "$Z/конкуренты/konkurenty.py" sbor proba_00 proba_01 --fake --rilsov 15 > /dev/null \
  && py "$Z/конкуренты/konkurenty.py" reiting > /dev/null && ls "$HOME/Projects/завод/конкуренты/"рейтинг-*.md > /dev/null && pass "конкуренты: поиск, сбор, рейтинг" || nope "конкуренты"
py "$Z/конкуренты/konkurenty.py" sbor proba_09 2>&1 | grep -q "только с --da" && pass "без --da денег не тратит" || nope "потолок денег"

echo; echo "ИТОГ: ✓ $ok, ✗ $fail"; [ "$fail" = 0 ]
