"""Выкладка через Buffer API без рук. Mac и Windows, только Python и curl. Ключ — BUFFER_API_KEY в .env.

  python3 -I vykladka.py kanaly                                     какие площадки подключены
  python3 -I vykladka.py post ВИДЕО.mp4 --text подпись.txt --kanal youtube [--kogda "2026-11-20 19:00"] [--tz +06:00]

Buffer берёт видео только по ссылке: файл заливается на временный хостинг (живёт от 1 часа до 3 суток),
поэтому отложенный пост дальше суток надёжнее через Cloudflare R2 (модули/выкладка.md). Готово — только когда Buffer вернул статус поста.
"""
import argparse, datetime, json, os, pathlib, re, subprocess, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.buffer.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
CREATE = """mutation($input: CreatePostInput!) { createPost(input: $input) { __typename
  ... on PostActionSuccess { post { id status } } ... on MutationError { message } } }"""
GET = "query($input: PostInput!) { post(input: $input) { id status externalLink error { message } } }"


def key():
    k = os.environ.get("BUFFER_API_KEY", "")
    env = ROOT / ".env"
    if not k and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("BUFFER_API_KEY="):
                k = line.split("=", 1)[1].split("#")[0].strip().strip('"')
    if not k:
        sys.exit("нет ключа: publish.buffer.com/settings/api → Personal Access → New Key, вставить в .env строкой BUFFER_API_KEY=")
    return k


def gql(q, v):
    req = urllib.request.Request(API, json.dumps({"query": q, "variables": v}).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key()}", "User-Agent": UA})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        return {"errors": [{"message": f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"}]}


def kanaly():
    orgs = gql("query { account { organizations { id } } }", {})
    out = []
    for o in ((orgs.get("data") or {}).get("account") or {}).get("organizations", []):
        r = gql("query($input: ChannelsInput!) { channels(input: $input) { id service name } }", {"input": {"organizationId": o["id"]}})
        out += (r.get("data") or {}).get("channels", [])
    if not out:
        sys.exit(f"каналов нет или ключ не подошёл: {orgs.get('errors') or 'подключи площадки на buffer.com'}")
    return out


def curl(args):
    return subprocess.run(["curl", "-sS", "-A", UA] + args, capture_output=True, text=True, timeout=900).stdout.strip()


def zalit(video):
    """Публичная ссылка на видео: перебор временных хостингов, проверка, что ссылка отдаёт видео."""
    def litterbox():
        u = curl(["-F", "reqtype=fileupload", "-F", "time=72h", "-F", f"fileToUpload=@{video}", "https://litterbox.catbox.moe/resources/internals/api.php"])
        return u if u.startswith("https://") else ""

    def uguu():
        return json.loads(curl(["-F", f"files[]=@{video}", "https://uguu.se/upload"]))["files"][0]["url"]

    def tmpfiles():
        u = json.loads(curl(["-F", f"file=@{video}", "https://tmpfiles.org/api/v1/upload"]))["data"]["url"]
        return u.replace("http://", "https://").replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)

    for fn in (litterbox, uguu, tmpfiles):
        try:
            u = fn()
        except (ValueError, KeyError, IndexError):
            continue
        if u and "video/" in curl(["-IL", u]).lower():
            return u
    sys.exit("✗ видео не залилось ни на один хостинг: проверь интернет или подключи R2 (модули/выкладка.md)")


def meta(service, text, title, ai):
    if service == "youtube":
        return {"youtube": {"title": (title or text.splitlines()[0])[:100], "categoryId": "22", "privacy": "public", "madeForKids": False, "isAiGenerated": ai}}
    if service == "tiktok":
        return {"tiktok": {"isAiGenerated": ai}}
    if service == "instagram":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": ai}}
    return {}


def post(a):
    ch = kanaly()
    c = next((x for x in ch if x["service"] == a.kanal), None)
    if not c:
        sys.exit(f"канал {a.kanal} не подключён. Есть: {', '.join(x['service'] for x in ch)}")
    text = pathlib.Path(a.text).read_text(encoding="utf-8").strip()
    url = zalit(a.video)
    print("видео залито:", url)
    item = {"channelId": c["id"], "text": text, "assets": [{"video": {"url": url, "metadata": {"thumbnailOffset": 0}}}], "metadata": meta(a.kanal, text, a.title, a.ai),
            "schedulingType": "automatic", "mode": "customScheduled" if a.kogda else "shareNow", "needsApproval": False}
    if a.kogda:
        when = datetime.datetime.strptime(a.kogda, "%Y-%m-%d %H:%M")
        item["dueAt"] = when.strftime("%Y-%m-%dT%H:%M:00") + a.tz
    r = gql(CREATE, {"input": item})
    res = (r.get("data") or {}).get("createPost") or {}
    if not res.get("post"):
        sys.exit(f"✗ Buffer не принял: {res.get('message') or r.get('errors')}")
    pid = res["post"]["id"]
    print(f"пост {pid}, статус {res['post']['status']}")
    if a.kogda:
        return
    for _ in range(40):  # «принят» — ещё не «вышел»: ждём ссылку на пост
        time.sleep(30)
        p = (gql(GET, {"input": {"id": pid}}).get("data") or {}).get("post") or {}
        st = (p.get("status") or "").lower()
        if st in ("sent", "published"):
            print("вышел:", p.get("externalLink"))
            return
        if st in ("error", "failed"):
            sys.exit(f"✗ площадка отказала: {(p.get('error') or {}).get('message')}")
    sys.exit("✗ за 20 минут пост не вышел: смотри очередь в Buffer")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
sub.add_parser("kanaly")
p = sub.add_parser("post")
p.add_argument("video"); p.add_argument("--text", required=True); p.add_argument("--kanal", required=True)
p.add_argument("--kogda"); p.add_argument("--tz", default="+00:00"); p.add_argument("--title"); p.add_argument("--ai", action="store_true", help="поставить площадкам метку «сделано ИИ»")
A = ap.parse_args()
if A.cmd == "kanaly":
    for c in kanaly():
        print(c["service"], c["name"], c["id"])
else:
    post(A)
