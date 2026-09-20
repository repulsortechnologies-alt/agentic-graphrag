import json, re

MONTHS = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
          'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
          'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'sep':9,
          'sept':9,'oct':10,'nov':11,'dec':12}

def parse_infobox(text):
    fields = {}
    if not text.startswith('[Infobox'):
        return fields
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('['):
            continue
        m = re.match(r'^([a-zA-Z_][a-zA-Z_0-9]*):\s*(.+)$', line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
        elif ':' not in line:
            break
    return fields

def parse_games(g):
    if not g: return (None, None)
    m = re.match(r'(\d{4})\s+(Summer|Winter)', g)
    return (int(m.group(1)), m.group(2)) if m else (None, None)

def parse_int(v):
    if not v: return None
    m = re.search(r'\d+', v.replace(',', ''))
    return int(m.group()) if m else None

def parse_date_iso(date_str, year):
    """Best-effort start-day ISO from many formats. Returns 'YYYY-MM-DD' or None."""
    if not date_str: return None
    yr_m = re.search(r'(19|20)\d{2}', date_str)
    yr = int(yr_m.group()) if yr_m else year
    if not yr: return None
    # 'day Month' e.g. '6 to 8 August', '23-26 August', '1 August'
    m = re.search(r'(\d{1,2})\s*[\u2013\u2014\-to ]*\s*(?:\d{1,2}\s+)?([A-Za-z]+)', date_str)
    if m and m.group(2).lower() in MONTHS:
        return f"{yr:04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    # 'Month day' e.g. 'August 18', 'August 21-22'
    m = re.search(r'([A-Za-z]+)\s+(\d{1,2})', date_str)
    if m and m.group(1).lower() in MONTHS:
        return f"{yr:04d}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return None

def extract_event(doc):
    """doc: corpus dict -> event record or None if it's a distractor (non-event)."""
    fb = parse_infobox(doc['text'])
    if not fb:
        return None
    year, season = parse_games(fb.get('games',''))
    # An Olympic event must have games + (medal or competitors)
    is_event = bool(year) and (fb.get('gold') or fb.get('competitors'))
    if not is_event:
        return None
    sm = re.match(r'(.+?) at the \d{4}', doc['title'])
    sport = sm.group(1) if sm else None
    date_raw = fb.get('date') or fb.get('dates')
    return {
        'qid': doc['doc_id'],
        'title': doc['title'],
        'url': doc.get('url'),
        'sport': sport,
        'event': fb.get('event'),
        'year': year, 'season': season,
        'games': f"{year} {season}" if year else None,
        'venue': fb.get('venue'),
        'date_raw': date_raw,
        'date_iso': parse_date_iso(date_raw, year),
        'competitors': parse_int(fb.get('competitors')),
        'nations': parse_int(fb.get('nations')),
        'gold': fb.get('gold'), 'goldNOC': fb.get('goldNOC'),
        'silver': fb.get('silver'), 'silverNOC': fb.get('silverNOC'),
        'bronze': fb.get('bronze'), 'bronzeNOC': fb.get('bronzeNOC'),
    }

def load_corpus(path):
    for line in open(path):
        yield json.loads(line)

if __name__ == '__main__':
    import sys
    src = sys.argv[1] if len(sys.argv)>1 else '/home/claude/dataset/hackathon-resources/corpus/corpus.jsonl'
    out = sys.argv[2] if len(sys.argv)>2 else '/home/claude/agentic-graphrag/data/events.jsonl'
    events=[]; distractors=0; total=0
    for doc in load_corpus(src):
        total+=1
        ev = extract_event(doc)
        if ev: events.append(ev)
        else: distractors+=1
    with open(out,'w') as f:
        for e in events: f.write(json.dumps(e, ensure_ascii=False)+'\n')
    dcov = sum(1 for e in events if e['date_iso'])
    print(f"total={total} events={len(events)} distractors={distractors}")
    print(f"date parsed: {dcov}/{len(events)} ({100*dcov/len(events):.0f}%)")
    print(f"-> {out}")
