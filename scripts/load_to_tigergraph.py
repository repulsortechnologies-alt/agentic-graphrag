#!/usr/bin/env python3
"""Load Olympic events into TigerGraph Savanna, then verify. macOS curl for TLS.
This version auto-probes several token-request formats and prints what the
server returns, so we can see which one your TigerGraph version accepts."""
import os, sys, json, time, subprocess, tempfile, urllib.parse

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
    print("no secret provided."); sys.exit(1)
if HOST.startswith("https://") and ":443" not in HOST:
    HOST = HOST + ":443"

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "events.jsonl")
events = [json.loads(l) for l in open(DATA)] if os.path.exists(DATA) else []
print("host:", HOST)
print("loaded %d events" % len(events))

def raw(method, path, body=None, token=None):
    """Return (http_status:int, text:str)."""
    args = ["curl", "-sS", "--tlsv1.2", "-o", "-", "-w", "\\n<<<%{http_code}>>>", "-X", method, HOST + path]
    if token:
        args += ["-H", "Authorization: Bearer " + token]
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
    text = out.stdout
    code = 0
    if "<<<" in text and ">>>" in text:
        try: code = int(text.split("<<<")[-1].split(">>>")[0])
        except: pass
        text = text.split("\n<<<")[0]
    return code, text

def try_token():
    q = urllib.parse.urlencode({"secret": SECRET, "lifetime": "2592000"})
    attempts = [
        ("POST", "/restpp/requesttoken", {"secret": SECRET, "lifetime": 2592000}),
        ("POST", "/restpp/requesttoken", {"secret": SECRET, "lifetime": "2592000"}),
        ("POST", "/restpp/requesttoken", {"secret": SECRET}),
        ("GET",  "/restpp/requesttoken?" + q, None),
        ("POST", "/gsql/v1/tokens", {"secret": SECRET, "lifetime": 2592000}),
        ("POST", "/api/restpp/requesttoken", {"secret": SECRET, "lifetime": 2592000}),
    ]
    for i, (m, p, b) in enumerate(attempts, 1):
        code, text = raw(m, p, b)
        snippet = text.replace("\n", " ")[:160]
        print("  [%d] %s %s -> HTTP %s | %s" % (i, m, p.split('?')[0], code, snippet))
        try:
            d = json.loads(text)
            tok = d.get("token") or d.get("results", {}).get("token")
            if tok:
                print("  -> token OK via attempt %d" % i)
                return tok
        except Exception:
            pass
    return None

print("probing token endpoints ...")
TOKEN = try_token()
if not TOKEN:
    print("\nNo token format worked. Paste this whole output back to Claude.")
    sys.exit(2)

def vattr(e):
    def V(x): return {"value": ("" if x is None else x)}
    return {"title": V(e.get("title")), "url": V(e.get("url")), "sport": V(e.get("sport")),
            "event": V(e.get("event")), "year": V(e.get("year") or 0), "season": V(e.get("season")),
            "venue": V(e.get("venue")), "date_iso": V(e.get("date_iso")),
            "competitors": V(e.get("competitors") or 0), "nations": V(e.get("nations") or 0)}

BATCH = 400; total = 0
for i in range(0, len(events), BATCH):
    chunk = events[i:i+BATCH]
    payload = {"vertices": {"Event": {e["qid"]: vattr(e) for e in chunk}}}
    code, text = raw("POST", "/restpp/graph/" + GRAPH, payload, TOKEN)
    if code != 200:
        print("upsert HTTP %s: %s" % (code, text[:200])); sys.exit(3)
    total += len(chunk); print("  upserted %d/%d" % (total, len(events))); time.sleep(0.1)
print("data load complete")

code, text = raw("GET", "/restpp/query/%s/findEvents?sport=Biathlon&year=2018&season=Winter&min_competitors=73" % GRAPH, None, TOKEN)
try:
    r = json.loads(text).get("results", [])
    n = len(r[0].get("events", [])) if r else 0
except Exception:
    n = -1
print("VERIFY findEvents(biathlon 2018 >73) = %d (expect 5) -> %s" % (n, "PASS" if n == 5 else "CHECK"))
