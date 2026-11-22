#!/bin/bash
# Чистая установка завода на «новом ученике» (поддельный HOME) — Mac/Linux. Windows так не проверить: см. тест-windows.md.
# Запуск: bash test/chistaya-ustanovka.sh <пустая папка> <папка пакета umnyi-claude> <папка с копиями montazh и instagram-parser>
#   третий аргумент — локальные git-копии монтажа и парсера (install.py --istochnik); без него они с GitHub;
#   «github» — и сам завод клонируется с GitHub (проверка того, что получит ученик).
# Денег не тратит: генерации и Apify — заглушки (--fake). Сеть нужна для pip, Node и npm (кэши берутся с настоящего HOME).
set -u
ZAVOD="$(cd "$(dirname "$0")/.." && pwd)"
BAZA="${1:?пустая папка}"; UMNYI="${2:?папка или ссылка пакета umnyi-claude}"; SRC="${3:-}"
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

Z="$HOME/.claude/skills/zavod"
if [ "$SRC" = "github" ]; then  # всё с GitHub, как у ученика: завод, монтаж, парсер
  echo "== 2. Завод с GitHub"; SRC=""
  git clone -q --depth 1 https://github.com/neuroakyl/neuroakyl-zavod "$Z" && pass "завод скачан с GitHub" || nope "git clone завода"
else
  echo "== 2. Завод (как git clone: только файлы репозитория)"
  mkdir -p "$Z"
  (cd "$ZAVOD" && git ls-files -co --exclude-standard -z | rsync -a --from0 --files-from=- ./ "$Z/")
fi
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
py "$Z/конкуренты/konkurenty.py" poisk "фитнес тренер онлайн" --fake --skolko 6 > /dev/null \
  && py "$Z/конкуренты/konkurenty.py" sbor proba_00 proba_01 --fake --rilsov 15 > /dev/null \
  && py "$Z/конкуренты/konkurenty.py" reiting > /dev/null && ls "$HOME/Projects/завод/конкуренты/"рейтинг-*.md > /dev/null && pass "конкуренты: поиск, сбор, рейтинг" || nope "конкуренты"
py "$Z/конкуренты/konkurenty.py" sbor proba_09 2>&1 | grep -q "сначала отбор" && pass "без утверждённого отбора конкурентов денег не тратит" || nope "отбор перед сбором"
py "$Z/конкуренты/konkurenty.py" sbor proba_09 --svoi 2>&1 | grep -q "только с --da" && pass "без --da денег не тратит" || nope "потолок денег"
PL="$HOME/Projects/завод/планы"; mkdir -p "$PL"
printf '%s' '{"mesyac":"2026-12","edinicy":[{"id":"R01","format":"reels","data":"2026-12-01","cel":"охват","tema":"т","huk":"Бир күндө он ролик.","huk_zapas":["а","б"],"yazyk":"ky","prizyv":"СӨЗ"},{"id":"T01","format":"threads","data":"2026-12-01","cel":"сообщество","tekst":"пост","yazyk":"ru"}]}' > "$PL/план-2026-12.json"
py "$Z/план/plan.py" dalshe 2>&1 | grep -q "не утверждён" && py "$Z/план/plan.py" proverit > /dev/null && py "$Z/план/plan.py" da > /dev/null \
  && py "$Z/план/plan.py" dalshe --format reels | grep -q '"R01"' && ls "$PL/план-2026-12.md" > /dev/null \
  && pass "контент-план: без «да» не выдаёт, после «да» даёт следующий пункт" || nope "контент-план очередью"

echo; echo "ИТОГ: ✓ $ok, ✗ $fail"; [ "$fail" = 0 ]
