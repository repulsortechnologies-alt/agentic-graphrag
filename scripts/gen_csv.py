import json, csv, re, sys, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
events=[json.loads(l) for l in open(f'{ROOT}/data/events.jsonl')]
D=f'{ROOT}/data'

def split_names(s):
    if not s: return []
    parts = re.split(r'(?<=[a-zéöüćğış])(?=[A-Z])', s)
    return [p.strip() for p in parts if p.strip()]

with open(f'{D}/event.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['qid','title','url','sport','event','year','season','venue','date_iso','competitors','nations'])
    for e in events:
        w.writerow([e['qid'],e['title'],e['url'],e['sport'],e['event'],e['year'],e['season'],
                    e['venue'],e['date_iso'],e['competitors'],e['nations']])
athletes=set(); venues=set(); games=set(); sports=set()
with open(f'{D}/edge_medals.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['qid','athlete','medal'])
    for e in events:
        for medal in ('gold','silver','bronze'):
            for name in split_names(e.get(medal)):
                w.writerow([e['qid'],name,medal]); athletes.add(name)
with open(f'{D}/edge_venue.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['qid','venue'])
    for e in events:
        if e['venue']: w.writerow([e['qid'],e['venue']]); venues.add(e['venue'])
with open(f'{D}/edge_games.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['qid','games','year','season'])
    for e in events:
        if e['games']: w.writerow([e['qid'],e['games'],e['year'],e['season']]); games.add(e['games'])
with open(f'{D}/edge_sport.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['qid','sport'])
    for e in events:
        if e['sport']: w.writerow([e['qid'],e['sport']]); sports.add(e['sport'])
print(f"CSVs: {len(events)} events, {len(athletes)} athletes, {len(venues)} venues, {len(games)} games, {len(sports)} sports")
