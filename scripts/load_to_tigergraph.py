"""Load Olympic events into TigerGraph Savanna via REST, then verify.
Run from your own terminal (reaches Savanna). Prereqs: schema+queries already
installed (done), and a Database Secret created in the Savanna UI.

  export TG_HOST=https://tg-b4c6211c-1b8c-4d36-bdf9-0cabf1683605.tg-2635877100.i.tgcloud.io
  export TG_SECRET=<paste the secret you created in Database Secrets>
  export TG_GRAPH=olympics
  python3 scripts/load_to_tigergraph.py
"""
import os, sys, json, time
try:
    import httpx
except ImportError:
    print("pip install httpx"); sys.exit(1)

HOST=os.environ.get("TG_HOST","").rstrip("/")
GRAPH=os.environ.get("TG_GRAPH","olympics")
SECRET=os.environ.get("TG_SECRET","")
if not HOST or not SECRET:
    print("set TG_HOST and TG_SECRET"); sys.exit(1)
if ":443" not in HOST and HOST.startswith("https://"):
    HOST=HOST+":443"

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
events=[json.loads(l) for l in open(f"{ROOT}/data/events.jsonl")]
print(f"loaded {len(events)} events from disk")

c=httpx.Client(timeout=60.0, verify=True)

# 1. mint token
r=c.post(f"{HOST}/restpp/requesttoken", json={"secret":SECRET,"lifetime":"2592000"})
tok=r.json().get("token") or r.json().get("results",{}).get("token")
if not tok:
    print("token mint failed:", r.status_code, r.text[:200]); sys.exit(2)
H={"Authorization":f"Bearer {tok}"}
print("token ok")

def vattr(e):
    def V(x): return {"value": ("" if x is None else x)}
    return {
        "title":V(e.get("title")), "url":V(e.get("url")), "sport":V(e.get("sport")),
        "event":V(e.get("event")), "year":V(e.get("year") or 0), "season":V(e.get("season")),
        "venue":V(e.get("venue")), "date_iso":V(e.get("date_iso")),
        "competitors":V(e.get("competitors") or 0), "nations":V(e.get("nations") or 0),
    }

# 2. upsert in batches
BATCH=400; total=0
for i in range(0, len(events), BATCH):
    chunk=events[i:i+BATCH]
    payload={"vertices":{"Event":{e["qid"]:vattr(e) for e in chunk}}}
    r=c.post(f"{HOST}/restpp/graph/{GRAPH}", headers=H, json=payload)
    if r.status_code!=200:
        print("upsert error", r.status_code, r.text[:200]); sys.exit(3)
    total+=len(chunk)
    print(f"  upserted {total}/{len(events)}")
    time.sleep(0.1)
print("data load complete")

# 3. verify with findEvents (biathlon 2018 >73 -> expect 5)
r=c.get(f"{HOST}/restpp/query/{GRAPH}/findEvents",
        params={"sport":"Biathlon","year":2018,"season":"Winter","min_competitors":73}, headers=H)
res=r.json().get("results",[])
n=len(res[0].get("events",[])) if res else 0
print(f"VERIFY findEvents(biathlon 2018 >73) = {n} events (expect 5) -> {'PASS' if n==5 else 'CHECK'}")
print("\nNext: export GRAPH_BACKEND=tigergraph && python3 scripts/benchmark.py")
