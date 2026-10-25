"""football-data.org에서 5대 리그 득점자를 받아 scorers.json으로 저장합니다."""
import json, os, sys, time, datetime, urllib.request, urllib.error

BASE = os.environ.get("FD_BASE", "https://api.football-data.org/v4")
KEY = os.environ["FOOTBALL_DATA_KEY"]
SLEEP = float(os.environ.get("FD_SLEEP", "7"))
CODES = ["PL", "PD", "SA", "BL1", "FL1"]


def get(path):
    for _ in range(4):
        req = urllib.request.Request(BASE + path, headers={"X-Auth-Token": KEY})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(30 if SLEEP else 0)
                continue
            sys.exit("HTTP %s: %s" % (e.code, path))
    sys.exit("재시도 실패: " + path)


out = []
for i, code in enumerate(CODES):
    data = get("/competitions/%s/scorers?limit=500" % code)
    for s in data.get("scorers", []):
        out.append({
            "player": {"name": s["player"]["name"]},
            "team": {"name": s["team"]["name"]},
            "playedMatches": s.get("playedMatches"),
            "goals": s.get("goals"),
            "assists": s.get("assists"),
        })
    print(code, len(data.get("scorers", [])))
    if i < len(CODES) - 1:
        time.sleep(SLEEP)

if not out:
    sys.exit("받은 데이터가 없어서 저장하지 않습니다.")
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open("scorers.json", "w", encoding="utf-8") as f:
    json.dump({"updated": now, "scorers": out}, f, ensure_ascii=False, separators=(",", ":"))
print("저장 완료:", len(out), "명")
