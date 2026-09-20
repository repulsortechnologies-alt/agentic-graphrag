#!/usr/bin/env python3
"""Load Olympic events into TigerGraph Savanna, then verify.
Uses macOS `curl` for HTTP (robust TLS) — no pip, no Python SSL issues.
Keep events.jsonl in the SAME folder as this script. Run:

  cd ~/Downloads
  python3 load_to_tigergraph.py      # it will prompt for your Database Secret
"""
import os, sys, json, time, subprocess, tempfile

DEFAULT_HOST = "https://tg-b4c6211c-1b8c-4d36-bdf9-0cabf1683605.tg-2635877100.i.tgcloud.io"
HOST = (os.environ.get("TG_HOST") or DEFAULT_HOST).rstrip("/")
GRAPH = os.environ.get("TG_GRAPH", "olympics")
SECRET = os.environ.get("TG_SECRET", "")
if not SECRET:
    try:
        SECRET = input("Paste your Database Secret and press Enter:\n").strip()
    except EOFError:
        SECRET = ""
if not SECRET:
    print("no secret provided; create one in Savanna > Database Secrets, then rerun."); sys.exit(1)
if HOST.startswith("https://") and ":443" not in HOST:
    HOST = HOST + ":443"

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "events.jsonl")
if not os.path.exists(DATA):
    print(f"events.jsonl not found next to this script ({DATA})"); sys.exit(1)
events = [json.loads(l) for l in open(DATA)]
print(f"loaded {len(events)} events")

def curl(method, path, body=None, token=None):
    """Call curl; return parsed JSON (or raise with stderr)."""
    args = ["curl", "-sS", "--tlsv1.2", "-X", method, HOST + path]
    if token:
        args += ["-H", f"Authorization: Bearer {token}"]
    tmp = None
    if body is not None:
        args += ["-H", "Content-Type: application/json"]
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(body, tmp); tmp.close()
        args += ["--data-binary", "@" + tmp.name]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=90)
    finally:
        if tmp: os.unlink(tmp.name)
    if out.returncode != 0:
        raise RuntimeError(f"curl failed ({out.returncode}): {out.stderr.strip()[:200]}")
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"non-JSON response: {out.stdout[:200]}")

# 1. mint RESTPP token
tokres = curl("POST", "/restpp/requesttoken", {"secret": SECRET, "lifetime": "2592000"})
TOKEN = tokres.get("token") or tokres.get("results", {}).get("token")
if not TOKEN:
    print("token mint failed:", tokres); sys.exit(2)
print("token ok")

def vattr(e):
    def V(x): return {"value": ("" if x is None else x)}
    return {"title": V(e.get("title")), "url": V(e.get("url")), "sport": V(e.get("sport")),
            "event": V(e.get("event")), "year": V(e.get("year") or 0), "season": V(e.get("season")),
            "venue": V(e.get("venue")), "date_iso": V(e.get("date_iso")),
            "competitors": V(e.get("competitors") or 0), "nations": V(e.get("nations") or 0)}

# 2. upsert Event vertices in batches
BATCH = 400; total = 0
for i in range(0, len(events), BATCH):
    chunk = events[i:i+BATCH]
    payload = {"vertices": {"Event": {e["qid"]: vattr(e) for e in chunk}}}
    try:
        curl("POST", f"/restpp/graph/{GRAPH}", payload, TOKEN)
    except Exception as ex:
        print("upsert error:", ex); sys.exit(3)
    total += len(chunk); print(f"  upserted {total}/{len(events)}"); time.sleep(0.1)
print("data load complete")

# 3. verify: biathlon 2018 Winter, >73 competitors -> expect 5
res = curl("GET", f"/restpp/query/{GRAPH}/findEvents?sport=Biathlon&year=2018&season=Winter&min_competitors=73",
           None, TOKEN)
r = res.get("results", [])
n = len(r[0].get("events", [])) if r else 0
print(f"VERIFY findEvents(biathlon 2018 >73) = {n} (expect 5) -> {'PASS' if n == 5 else 'CHECK'}")
print("\nGraph loaded. If PASS, your TigerGraph backend is fully wired.")
