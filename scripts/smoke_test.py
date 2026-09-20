"""Standalone Savanna connectivity + query smoke test.
Usage:
  export TG_HOST=https://YOUR-DOMAIN.i.tgcloud.io:443
  export TG_SECRET=your_secret_from_admin_portal
  export TG_GRAPH=olympics
  python3 scripts/smoke_test.py
Prints: token mint status, then runs findEvents for a known question and checks the answer."""
import os, sys, json
try:
    import httpx
except ImportError:
    print("pip install httpx"); sys.exit(1)

HOST=os.environ.get("TG_HOST","").rstrip("/")
GRAPH=os.environ.get("TG_GRAPH","olympics")
SECRET=os.environ.get("TG_SECRET","")
TOKEN=os.environ.get("TG_TOKEN","")
if not HOST:
    print("set TG_HOST (and TG_SECRET or TG_TOKEN)"); sys.exit(1)

c=httpx.Client(timeout=30.0, verify=True)

if not TOKEN:
    print(f"[1] minting RESTPP token at {HOST}/restpp/requesttoken ...")
    r=c.post(f"{HOST}/restpp/requesttoken", json={"secret":SECRET,"lifetime":"1000000"})
    print("    status", r.status_code, r.text[:160])
    TOKEN=r.json().get("token") or r.json().get("results",{}).get("token")
    if not TOKEN:
        print("    !! no token — check secret / host / port 443"); sys.exit(2)
    print("    token ok")

H={"Authorization":f"Bearer {TOKEN}"}
print(f"[2] GET findEvents (biathlon 2018 Winter, competitors>73 -> expect 5 events)")
r=c.get(f"{HOST}/restpp/query/{GRAPH}/findEvents",
        params={"sport":"Biathlon","year":2018,"season":"Winter","min_competitors":73}, headers=H)
print("    status", r.status_code)
try:
    res=r.json().get("results",[])
    events=res[0].get("events",[]) if res else []
    print(f"    findEvents returned {len(events)} events (expect 5)")
    print("    PASS" if len(events)==5 else "    check load / query install")
except Exception as e:
    print("    parse error:", e, r.text[:200])
print("[3] listSports")
r=c.get(f"{HOST}/restpp/query/{GRAPH}/listSports", headers=H)
try: print("    sports:", len(r.json().get("results",[{}])[0].get("sports",[])))
except: print("   ", r.status_code, r.text[:120])
