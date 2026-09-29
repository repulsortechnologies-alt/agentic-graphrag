#!/usr/bin/env python3
"""Live demo: Agentic GraphRAG on TigerGraph Savanna. Self-contained, curl-based."""
import os, sys, json, re, subprocess, tempfile, urllib.parse
HOST="https://tg-b4c6211c-1b8c-4d36-bdf9-0cabf1683605.tg-2635877100.i.tgcloud.io:443"
GRAPH="olympics"
SECRET=os.environ.get("TG_SECRET") or input("Paste your Database Secret:\n").strip()
def curl(method,path,body=None,token=None):
    a=["curl","-sS","--tlsv1.2","-o","-","-w","\\n<<<%{http_code}>>>","-X",method,HOST+path]
    if token:a+=["-H","Authorization: Bearer "+token]
    tmp=None
    if body is not None:
        a+=["-H","Content-Type: application/json"]
        tmp=tempfile.NamedTemporaryFile("w",suffix=".json",delete=False);json.dump(body,tmp);tmp.close();a+=["--data-binary","@"+tmp.name]
    try:out=subprocess.run(a,capture_output=True,text=True,timeout=60)
    finally:
        if tmp:os.unlink(tmp.name)
    t=out.stdout
    if "<<<" in t:t=t.split("\n<<<")[0]
    try:return json.loads(t)
    except:return {"_raw":t[:200]}
TOKEN=curl("POST","/gsql/v1/tokens",{"secret":SECRET,"lifetime":2592000}).get("token")
if not TOKEN:print("token failed");sys.exit(1)
DEF={"sport":"","year":0,"season":"","venue":"","date_iso":"","min_competitors":0,"max_competitors":0,"min_nations":0,"event_contains":""}
def find(**kw):
    p=dict(DEF);p.update({k:v for k,v in kw.items() if v is not None})
    r=curl("GET","/restpp/query/%s/findEvents?%s"%(GRAPH,urllib.parse.urlencode(p,quote_via=urllib.parse.quote)),None,TOKEN).get("results",[])
    return [e["attributes"] for e in (r[0].get("events",[]) if r else [])]
def years(season):
    r=curl("GET","/restpp/query/%s/gamesYears?season=%s"%(GRAPH,season),None,TOKEN).get("results",[])
    return sorted(r[0].get("years",[])) if r else []
def norm(s):
    s=re.sub(r"(\d+)\s*kg",r"\1kg",(s or "").lower()); s=s.replace("'","").replace("-"," ")
    return re.sub(r"\s+"," ",s).strip()
def gender(s):
    s=(s or "").lower()
    return "w" if ("women" in s or "ladies" in s) else ("m" if "men" in s else None)
def pick(rows,desc):
    if not desc:return rows[0] if rows else None
    best=None;bs=-1;gd=gender(desc);nums={t for t in norm(desc).split() if any(c.isdigit() for c in t)}
    for e in rows:
        ge=gender(e.get("event"))
        if gd and ge and gd!=ge:continue
        et=set(norm(e.get("event")).split());sc=len(set(norm(desc).split())&et)
        if nums and nums<=et:sc+=5*len(nums)
        if sc>bs:bs=sc;best=e
    return best
def answer(q):
    ql=q.lower()
    m=re.search(r'how many (.+?) events at the (\d{4}) (summer|winter) olympics had more than (\d+) competitors',ql)
    if m:return "aggregation",str(len(find(sport=m.group(1),year=int(m.group(2)),season=m.group(3).capitalize(),min_competitors=int(m.group(4)))))
    m=re.search(r'which (.+?) event at the (\d{4}) (summer|winter) olympics had the highest number of competitors',ql)
    if m:
        ev=find(sport=m.group(1),year=int(m.group(2)),season=m.group(3).capitalize())
        return "superlative",(max(ev,key=lambda e:e["competitors"])["title"] if ev else "")
    m=re.search(r'gold medal in the (.+?) event at the (summer|winter) olympics held immediately before (\d{4})',ql)
    if m:
        seas=m.group(2).capitalize();desc=m.group(1);ys=[y for y in years(seas) if y<int(m.group(3))]
        if not ys:return "temporal",""
        toks=desc.split();ev=find(sport=toks[-1],year=max(ys),season=seas)
        best=pick(ev," ".join(toks));return "temporal",(best["gold"] if best else "")
    m=re.search(r'gold medal in the event held at (.+?) on (.+?)(?: at the (\d{4}).*)?$',ql)
    if m:
        venue=m.group(1);yr=int(m.group(3)) if m.group(3) else (int(re.search(r'(19|20)\d{2}',m.group(2)).group()) if re.search(r'(19|20)\d{2}',m.group(2)) else 0)
        MO={"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
        dm=re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})|([a-z]+)\s+(\d{1,2})",m.group(2))
        diso=""
        if dm and dm.group(2) and dm.group(2) in MO: diso="%s-%02d-%02d"%(dm.group(3),MO[dm.group(2)],int(dm.group(1)))
        elif dm and dm.group(4) and dm.group(4) in MO: diso="%s-%02d-%02d"%(yr,MO[dm.group(4)],int(dm.group(5)))
        ev=find(venue=venue,date_iso=diso) or find(venue=venue,year=yr)
        return "multi_hop",(ev[0]["gold"] if ev else "")
    m=re.search(r'how many nations competed in (.+?)(?:\?|$)',ql)
    if m:
        t=m.group(1);sm=re.match(r'(.+?) at the (\d{4})',t)
        sport=sm.group(1) if sm else "";yr=int(sm.group(2)) if sm else 0
        seas="Summer" if "summer" in t else ("Winter" if "winter" in t else "")
        core=re.split(r"olympics",t)[-1].strip(" –—-")
        ev=find(sport=sport,year=yr,season=seas);best=pick(ev,core)
        return "lookup",(str(best["nations"]) if best else "")
    return "?",""
QS=[("According to the provided corpus, how many biathlon events at the 2018 Winter Olympics had more than 73 competitors?","5"),
    ("According to the provided corpus, which athletics event at the 2008 Summer Olympics had the highest number of competitors?","marathon"),
    ("How many nations competed in Sailing at the 2016 Summer Olympics – Women's RS:X?","26"),
    ("Who won the gold medal in the men's 20 kilometres walk athletics event at the Summer Olympics held immediately before 2016?","Chen Ding"),
    ("Who won the gold medal in the event held at Olympic Weightlifting Gymnasium on 20 September 1988?","Naim")]
print("\n=== Agentic GraphRAG on TigerGraph Savanna ===\n")
ok=0
for q,gold in QS:
    qt,ans=answer(q);good=norm(gold) in norm(ans);ok+=good
    print("[%s] %s"%(qt,q[:66]))
    print("   -> %s   %s\n"%((ans or "(none)")[:48],"OK" if good else "(want ~%s)"%gold))
print("%d/%d correct, all computed live on TigerGraph."%(ok,len(QS)))
