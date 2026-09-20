"""Execute a structured plan against the graph backend -> answer + evidence.
This is where the graph does deterministic compute (count/argmax/filter/join).
refine_multihop() is the agentic-only precise path that disambiguates
venue+date collisions (a venue hosts many events) using the infobox date
string and, for true ties, a vector tiebreak."""
from __future__ import annotations
import re
from src.graph.backend import norm


def execute(plan, backend):
    op = plan['op']; P = plan['params']
    ev = []

    if op == "count":
        rows = backend.find_events(sport=P.get('sport'), year=P.get('year'), season=P.get('season'),
                                   min_competitors=P.get('min_competitors'))
        ev = [r['qid'] for r in rows]
        return str(len(rows)), ev

    if op in ("argmax", "argmin"):
        rows = backend.find_events(sport=P.get('sport'), year=P.get('year'), season=P.get('season'))
        if not rows:
            return "", []
        metric = plan.get('metric', 'competitors')
        key = lambda r: (r.get(metric) if r.get(metric) is not None else -1)
        best = (max if op == "argmax" else min)(rows, key=key)
        return best['title'], [best['qid']]

    if op == "temporal_gold":
        seas = P.get('season')
        years = [y for y in backend.games_years(seas)
                 if (y < P['pivot_year'] if P['direction'] == 'before' else y > P['pivot_year'])]
        if not years:
            return "", []
        target = max(years) if P['direction'] == 'before' else min(years)
        # fetch all sport events that year, rank by robust event similarity
        rows = backend.find_events(sport=P.get('sport'), year=target, season=seas)
        best = _pick_event(rows, P.get('event_contains'))
        if not best:
            return "", []
        return best.get('gold') or "", [best['qid']]

    if op == "venue_date_gold":
        rows = backend.find_events(venue=P.get('venue'), date_iso=P.get('date_iso'), year=P.get('year'))
        if not rows:
            rows = backend.find_events(venue=P.get('venue'), year=P.get('year'))
        if not rows:
            return "", []
        return rows[0].get('gold') or "", [rows[0]['qid']]

    if op == "title_field":
        row = _resolve_title(backend, P.get('title'))
        if not row:
            return "", []
        val = row.get(plan['answer_field'])
        return (str(val) if val is not None else ""), [row['qid']]

    return "", []


def _norm_event(s):
    """Normalize event strings so '68 kg' == '68kg', drop apostrophes/punct."""
    s = norm(s)
    s = re.sub(r"(\d+)\s*kg", r"\1kg", s)          # 68 kg -> 68kg
    s = re.sub(r"(\d+)\s*(m|metre|metres|meter|meters)\b", r"\1m", s)
    s = s.replace("'", "").replace("-", " ")
    return s


def _gender(s):
    s = norm(s)
    if re.search(r"\bwomen", s) or re.search(r"\bladies", s):
        return "w"
    if re.search(r"\bmen", s):
        return "m"
    return None


def _event_similarity(query_desc, event_str):
    """Higher = better. Disqualifies (-1) on gender mismatch."""
    qn, en = _norm_event(query_desc), _norm_event(event_str)
    gq, ge = _gender(query_desc), _gender(event_str)
    if gq and ge and gq != ge:
        return -1
    qtok, etok = set(qn.split()), set(en.split())
    score = len(qtok & etok)
    # strong bonus when all numeric tokens in the query appear in the event
    qnums = {t for t in qtok if any(c.isdigit() for c in t)}
    if qnums and qnums <= etok:
        score += 5 * len(qnums)
    if gq and ge and gq == ge:
        score += 1
    return score


def _pick_event(rows, desc):
    """Pick the single event best matching a description (gender + number aware)."""
    if not rows:
        return None
    if not desc:
        return rows[0]
    scored = [(r, _event_similarity(desc, r.get('event', ''))) for r in rows]
    scored = [(r, s) for r, s in scored if s >= 0]
    if not scored:
        return None
    scored.sort(key=lambda x: -x[1])
    return scored[0][0]


def _resolve_title(backend, title):
    """Match a full event title to one event, enforcing gender + numeric tokens."""
    events = backend.events if hasattr(backend, 'events') else []
    scored = []
    for e in events:
        combo = e['title'] + " " + (e.get('event') or "")
        s = _event_similarity(title, combo)
        # also credit sport/year/season tokens from the title
        s += _overlap(_norm_event(e['title']), _norm_event(title))
        if s >= 0:
            scored.append((e, s))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[1])
    return scored[0][0]


def _overlap(a, b):
    return len(set(a.split()) & set(b.split()))


# ---- Agentic refinement: disambiguate venue+date collisions ----
def _date_score(qdate, edate):
    if not edate or not qdate:
        return -1
    qn, en = norm(qdate), norm(edate)
    if qn == en:
        return 100
    qtok = set(re.findall(r"\w+", qn)); etok = set(re.findall(r"\w+", en))
    if qtok and qtok <= etok:
        return 50 + len(qtok)
    return len(qtok & etok)


_Q_DATE = re.compile(r"held at .+? on (.+?)(?: at the \d{4} (?:summer|winter) olympics)?\??$", re.I)


def refine_multihop(plan, backend, retriever, question):
    """Return (answer, evidence, note, n_candidates). Agentic-only precise path."""
    P = plan['params']
    cands = (backend.find_events(venue=P.get('venue'), year=P.get('year'))
             if P.get('year') else backend.find_events(venue=P.get('venue')))
    if not cands:
        return "", [], "no_candidates", 0
    n = len(cands)
    m = _Q_DATE.search(question.strip())
    qdate = m.group(1).strip() if m else (P.get('date_iso') or "")
    scored = sorted(cands, key=lambda c: -_date_score(qdate, c.get('date_raw')))
    topscore = _date_score(qdate, scored[0].get('date_raw'))
    ties = [c for c in scored if _date_score(qdate, c.get('date_raw')) == topscore]
    if len(ties) > 1 and retriever is not None:
        hits = retriever.search(question, k=10)
        rank = {h['doc_id']: i for i, h in enumerate(hits)}
        ties.sort(key=lambda c: rank.get(c['qid'], 999))
        top = ties[0]
        return top.get('gold') or "", [top['qid']], f"date_tie_vector_break(n={n})", n
    top = scored[0]
    return top.get('gold') or "", [top['qid']], f"date_disambiguated(n={n})", n
