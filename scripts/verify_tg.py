#!/usr/bin/env python3
"""Quick check that findEvents works over REST with all params supplied. No data upload."""
import os, sys, json, subprocess, tempfile, urllib.parse
HOST = "https://tg-b4c6211c-1b8c-4d36-bdf9-0cabf1683605.tg-2635877100.i.tgcloud.io:443"
GRAPH = "olympics"
SECRET = os.environ.get("TG_SECRET") or input("Paste your Database Secret:\n").strip()
def curl(method, path, body=None, token=None):
    args=["curl","-sS","--tlsv1.2","-o","-","-w","\\n<<<%{http_code}>>>","-X",method,HOST+path]
    if token: args+=["-H","Authorization: Bearer "+token]
    tmp=None
    if body is not None:
        args+=["-H","Content-Type: application/json"]
        tmp=tempfile.NamedTemporaryFile("w",suffix=".json",delete=False); json.dump(body,tmp); tmp.close()
        args+=["--data-binary","@"+tmp.name]
    try: out=subprocess.run(args,capture_output=True,text=True,timeout=60)
    finally:
        if tmp: os.unlink(tmp.name)
    t=out.stdout; code=0
    if "<<<" in t: 
        try: code=int(t.split("<<<")[-1].split(">>>")[0])
        except: pass
        t=t.split("\n<<<")[0]
    return code,t
tok=json.loads(curl("POST","/gsql/v1/tokens",{"secret":SECRET,"lifetime":2592000})[1]).get("token")
print("token ok" if tok else "TOKEN FAIL")
# all 9 params supplied, defaults for unfiltered
allp={"sport":"Biathlon","year":2018,"season":"Winter","venue":"","date_iso":"",
      "min_competitors":73,"max_competitors":0,"min_nations":0,"event_contains":""}
q=urllib.parse.urlencode(allp)
code,t=curl("GET","/restpp/query/%s/findEvents?%s"%(GRAPH,q),None,tok)
try:
    r=json.loads(t).get("results",[]); n=len(r[0].get("events",[])) if r else 0
except Exception: n=-1; 
print("findEvents(biathlon 2018 >73, ALL params) = %s  (expect 5) -> %s"%(n,"PASS" if n==5 else "FAIL"))
if n!=5: print("raw:", t[:300])
