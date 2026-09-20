"""Answer reader: extract answer from retrieved doc context.
Offline: deterministic infobox reader (genuinely answers single-doc lookups).
With key: LLM reader. RAG uses this over retrieved text."""
from __future__ import annotations
import re
from src.graph.extract import parse_infobox

def _clean(v): return re.sub(r'\s+',' ',(v or '').strip())

def infobox_reader(question, contexts):
    """contexts: list of {title,text}. Return best-effort short answer string."""
    q = question.lower()
    top = contexts[0] if contexts else None
    if not top: return ""
    fb = parse_infobox(top['text'])
    # field routing by question intent
    if 'gold' in q or 'won' in q and 'medal' in q:
        return _clean(fb.get('gold'))
    if 'silver' in q: return _clean(fb.get('silver'))
    if 'bronze' in q: return _clean(fb.get('bronze'))
    if 'how many nation' in q or 'number of nation' in q: return _clean(fb.get('nations'))
    if 'how many competitor' in q or 'number of competitor' in q: return _clean(fb.get('competitors'))
    if 'venue' in q or 'where' in q: return _clean(fb.get('venue'))
    if 'when' in q or 'date' in q: return _clean(fb.get('date') or fb.get('dates'))
    # default: gold medalist (most common question)
    return _clean(fb.get('gold'))

def llm_reader(llm, question, contexts, model):
    ctx = "\n\n".join(f"[{c['title']}]\n{c['text'][:1200]}" for c in contexts[:5])
    prompt = (f"Answer the question using ONLY the context. Reply with just the answer, no explanation.\n\n"
              f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer:")
    return llm.complete(prompt, model=model, json_out=False).strip()
