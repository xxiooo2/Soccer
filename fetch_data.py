"""football-data.org에서 득점자·순위·경기 결과를 받아 scorers.json, tables.json으로 저장합니다."""
import json, os, re, sys, time, datetime, unicodedata, difflib, urllib.request, urllib.error

BASE = os.environ.get("FD_BASE", "https://api.football-data.org/v4")
KEY = os.environ["FOOTBALL_DATA_KEY"]
SLEEP = float(os.environ.get("FD_SLEEP", "7"))
CODES = ["PL", "PD", "SA", "BL1", "FL1", "CL"]  # 앱의 리그 순서와 같아야 해요
SCORER_CODES = CODES[:5]
EXTRA = ["Club Brugge", "Sporting CP", "Porto", "Shakhtar Donetsk", "PSV", "Feyenoord", "LASK",
         "Bodø/Glimt", "Viking", "AEK Athens", "Slavia Prague", "Galatasaray", "Fenerbahçe",
         "Sabah", "Slovan Bratislava"]
ALIAS = {"sporting clube de portugal": "Sporting CP", "slavia praha": "Slavia Prague"}
TEAMS = json.load(open("teams.json", encoding="utf-8")) if os.path.exists("teams.json") else {}
_last = [0.0]


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("ø", "o"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(w for w in s.split() if w not in ("fc", "sk", "kv", "fk", "ac", "cf", "sc", "as", "afc"))


def mapname(t):
    name = t.get("name") or ""
    if name in TEAMS:
        return TEAMS[name]
    n = norm(name)
    for k, v in ALIAS.items():
        if norm(k) in n:
            return v
    for e in EXTRA:
        en = norm(e)
        if en and (en in n or difflib.SequenceMatcher(None, en, n).ratio() >= 0.8):
            return e
    return t.get("shortName") or name


def get(path):
    wait = SLEEP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    for _ in range(3):
        req = urllib.request.Request(BASE + path, headers={"X-Auth-Token": KEY})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                _last[0] = time.time()
                return json.load(r)
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            print("  HTTP", e.code, path)
            if e.code == 429:
                time.sleep(60 if SLEEP else 0)
                continue
            return None
        except Exception as e:
            print("  오류", e, path)
            return None
    return None


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ok = 0

# 1) 득점자
scorers = []
got = 0
for code in SCORER_CODES:
    d = get("/competitions/%s/scorers?limit=500" % code)
    if not d:
        continue
    got += 1
    for s in d.get("scorers", []):
        scorers.append({"player": {"name": s["player"]["name"]}, "team": {"name": s["team"]["name"]},
                        "playedMatches": s.get("playedMatches"), "goals": s.get("goals"),
                        "assists": s.get("assists")})
    print("득점자", code, len(d.get("scorers", [])))
if got == len(SCORER_CODES) and scorers:
    json.dump({"updated": now, "scorers": scorers}, open("scorers.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    ok += 1
else:
    print("득점자는 일부만 받아서 저장하지 않았어요.")

# 2) 순위·경기 (실패한 대회는 예전 값을 그대로 둬요)
old = load("tables.json", {})
st = old.get("st") or [[] for _ in CODES]
st += [[] for _ in range(len(CODES) - len(st))]
games = {}
for g in old.get("g", []):
    games.setdefault(g[0], []).append(g)
changed = 0
for i, code in enumerate(CODES):
    d = get("/competitions/%s/standings" % code)
    if d and d.get("standings"):
        tabs = [t for t in d["standings"] if t.get("type") == "TOTAL"] or d["standings"]
        stage = [t for t in tabs if t.get("stage") == "LEAGUE_STAGE"]
        table = (stage or tabs)[0].get("table", [])
        rows = [[mapname(r["team"]), r.get("won", 0), r.get("draw", 0), r.get("lost", 0), r.get("points", 0)]
                for r in table]
        if rows:
            st[i] = rows
            changed += 1
            print("순위", code, len(rows))
    m = get("/competitions/%s/matches" % code)
    if m and m.get("matches") is not None:
        fin, up = [], []
        for x in m["matches"]:
            h, a = mapname(x["homeTeam"]), mapname(x["awayTeam"])
            utc = x.get("utcDate")
            if not (h and a and utc):
                continue
            ft = (x.get("score") or {}).get("fullTime") or {}
            if x.get("status") == "FINISHED" and ft.get("home") is not None:
                fin.append([i, "F", utc, h, a, ft["home"], ft["away"]])
            elif x.get("status") in ("SCHEDULED", "TIMED"):
                up.append([i, "S", utc, h, a, None, None])
        fin.sort(key=lambda g: g[2])
        up.sort(key=lambda g: g[2])
        games[i] = fin[-10:] + up[:10]
        changed += 1
        print("경기", code, len(games[i]))
if changed:
    allg = [g for k in sorted(games) for g in games[k]]
    json.dump({"updated": now, "st": st, "g": allg}, open("tables.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    ok += 1
if not ok:
    sys.exit("저장된 데이터가 없어요. 키와 요금제를 확인하세요.")
print("완료")
