"""Question -> structured query plan. The 'brain' that turns NL into graph ops.
Heuristic planner works offline & deterministically; LLM planner generalizes.
A plan: {qtype, op, params, answer_field}."""
from __future__ import annotations
import re
from src.graph.extract import parse_date_iso, MONTHS

SEASON = {'summer':'Summer','winter':'Winter'}

def _year(s):
    m=re.search(r'\b(19|20)\d{2}\b', s); return int(m.group()) if m else None

def _season(s):
    for k,v in SEASON.items():
        if k in s.lower(): return v
    return None

def heuristic_plan(question):
    q = question.strip(); ql = q.lower()

    # AGGREGATION: how many {sport} events ... more than N competitors
    m = re.search(r'how many (.+?) events at the (\d{4}) (summer|winter) olympics had more than (\d+) competitors', ql)
    if m:
        return {"qtype":"aggregation","op":"count",
                "params":{"sport":m.group(1).strip(),"year":int(m.group(2)),
                          "season":SEASON[m.group(3)],"min_competitors":int(m.group(4))},
                "answer_field":"count"}

    # SUPERLATIVE: which {sport} event ... highest/lowest number of competitors
    m = re.search(r'which (.+?) event at the (\d{4}) (summer|winter) olympics had the (highest|lowest) number of competitors', ql)
    if m:
        return {"qtype":"superlative","op":"argmax" if m.group(4)=="highest" else "argmin",
                "params":{"sport":m.group(1).strip(),"year":int(m.group(2)),"season":SEASON[m.group(3)]},
                "answer_field":"title","metric":"competitors"}

    # TEMPORAL: gold in {event} at the Summer Olympics held immediately before/after {year}
    m = re.search(r'gold medal in the (.+?) event at the (summer|winter) olympics held immediately (before|after) (\d{4})', ql)
    if m:
        desc, seas, direction, yr = m.group(1), SEASON[m.group(2)], m.group(3), int(m.group(4))
        sport, ev = _split_event_desc(desc)
        return {"qtype":"temporal","op":"temporal_gold",
                "params":{"sport":sport,"event_contains":ev,"season":seas,
                          "direction":direction,"pivot_year":yr},
                "answer_field":"gold"}

    # MULTI_HOP: gold in the event held at {venue} on {date}[ at the {year} {season} Olympics]
    m = re.search(r'gold medal in the event held at (.+?) on (.+?)(?: at the (\d{4}) (summer|winter) olympics)?\?*$', ql, re.I)
    if m:
        venue, date_raw = m.group(1).strip(), m.group(2).strip()
        yr = int(m.group(3)) if m.group(3) else _year(date_raw)
        date_iso = parse_date_iso(date_raw, yr)
        return {"qtype":"multi_hop","op":"venue_date_gold",
                "params":{"venue":venue,"date_iso":date_iso,"year":yr},
                "answer_field":"gold"}

    # LOOKUP: how many nations/competitors competed in {full event title}
    m = re.search(r'how many (nations|competitors) (?:competed|were there) in (.+?)\?*$', ql)
    if m:
        field = 'nations' if m.group(1)=='nations' else 'competitors'
        return {"qtype":"lookup","op":"title_field","params":{"title":m.group(2).strip()},"answer_field":field}
    # LOOKUP generic: who won gold in {title}
    m = re.search(r'who won the (gold|silver|bronze) medal in (.+?)\?*$', ql)
    if m:
        return {"qtype":"lookup","op":"title_field","params":{"title":m.group(2).strip()},"answer_field":m.group(1)}

    return {"qtype":"lookup","op":"fallback","params":{"query":q},"answer_field":"gold"}

def _split_event_desc(desc):
    """'men's 20 kilometres walk athletics' -> (sport='athletics', event_contains='men's 20 kilometres walk')
    sport = last token(s) that name a sport; we take the final word group before end."""
    desc = desc.strip()
    # sport is typically the trailing word(s); known multiword sports
    for sp in ('cross-country skiing','alpine skiing','speed skating','figure skating',
               'short track speed skating','artistic gymnastics','artistic swimming',
               'nordic combined','freestyle skiing'):
        if desc.endswith(sp):
            return sp, desc[:-len(sp)].strip()
    toks = desc.split()
    return toks[-1], " ".join(toks[:-1]).strip()

# ---- LLM planner (used when GEMINI key present; generalizes beyond templates) ----
PLAN_SYS = """You convert an Olympic-events question into a JSON query plan.
Fields: qtype (lookup|multi_hop|temporal|aggregation|superlative), op, params, answer_field.
Ops and params mirror these examples. Return ONLY JSON."""

def llm_plan(llm, question, model):
    import json
    ex = ('{"qtype":"aggregation","op":"count","params":{"sport":"Shooting","year":2004,'
          '"season":"Summer","min_competitors":37},"answer_field":"count"}')
    prompt = f"Examples of a plan:\n{ex}\n\nQuestion: {question}\nPlan JSON:"
    try:
        d = json.loads(llm.complete(prompt, system=PLAN_SYS, model=model, json_out=True))
        if 'qtype' in d and 'op' in d: return d
    except Exception:
        pass
    return heuristic_plan(question)
