"""Agentic orchestrator: multi-step investigation with state, evidence,
self-correction, cross-source verification, and explicit stopping criteria.
Unlike GraphRAG (fixed plan->execute), this evaluates evidence, detects gaps,
switches strategy, and verifies against a second source before answering."""
from __future__ import annotations
from src.agents.planner import heuristic_plan, llm_plan
from src.agents.executor import execute, refine_multihop
from src.pipelines.reader import infobox_reader
from src.graph.backend import norm
from src.utils.cost import est, SCAFFOLD

MAX_TURNS = 6

class State:
    def __init__(self, question):
        self.question=question; self.evidence=[]; self.trace=[]
        self.answer=None; self.confidence=0.0; self.turns=0; self.gaps=[]; self.tok=SCAFFOLD['agentic']+est(len(question))
    def log(self, action, **kw):
        self.trace.append({"turn":self.turns,"action":action,**kw})

def run(question, backend, retriever=None, llm=None, use_llm_planner=False, model=None):
    st = State(question)

    # 1. PLAN — decompose question into a structured investigation
    plan = llm_plan(llm, question, model) if (use_llm_planner and llm) else heuristic_plan(question)
    st.log("plan", qtype=plan['qtype'], op=plan['op'], params=plan['params'])
    st.turns += 1

    # 2. ROUTE + EXECUTE primary (graph)
    answer, ev = execute(plan, backend)
    st.log("graph_execute", op=plan['op'], result=answer, evidence_docs=ev)
    st.evidence += ev; st.turns += 1

    # 2b. REFINE — multi_hop venue+date collisions need disambiguation
    #     (a venue hosts many events; GraphRAG takes the first, the agent picks the right one)
    if plan['op'] == "venue_date_gold":
        r_ans, r_ev, note, ncand = refine_multihop(plan, backend, retriever, question)
        st.log("refine_multihop", candidates=ncand, strategy=note, result=r_ans)
        st.turns += 1
        if r_ans:
            if ncand > 1 and norm(r_ans) != norm(answer):
                st.gaps.append(f"venue+date matched {ncand} events; disambiguated by date/vector")
            answer, ev = r_ans, r_ev
            st.evidence += [e for e in r_ev if e not in st.evidence]

    # 3. JUDGE — is the evidence sufficient?
    empty = (answer == "" or answer is None or (plan['op']=='count' and not ev and answer=='0' and False))
    if empty or not ev:
        st.gaps.append("primary retrieval returned no grounded evidence")
        st.log("judge", verdict="insufficient", reason="empty result or no evidence docs")
        st.turns += 1
        # 4. SELF-CORRECT — relax constraints / switch strategy
        answer, ev = _recover(plan, backend, retriever, question, st)
    else:
        st.log("judge", verdict="grounded", evidence_count=len(ev))
        st.turns += 1

    # 5. VERIFY — cross-check single-fact answers against vector retrieval
    if plan['qtype'] in ("lookup","multi_hop","temporal") and retriever is not None and answer:
        st.confidence = _verify(answer, ev, backend, retriever, question, st)
    else:
        # aggregation/superlative: confidence from deterministic graph coverage
        st.confidence = 0.9 if ev else 0.3

    st.answer = answer
    st.log("stop", reason="confident" if st.confidence>=0.66 else "max_evidence", confidence=round(st.confidence,2))
    return {"answer":answer, "evidence":st.evidence, "plan":plan,
            "confidence":round(st.confidence,3), "gaps":st.gaps,
            "est_tokens":st.tok, "turns":st.turns, "trace":st.trace}

def _recover(plan, backend, retriever, question, st):
    """Strategy switches when primary fails."""
    P=plan['params']
    if plan['op']=="venue_date_gold":
        # relax exact date -> venue+year, then venue only
        for relax in [dict(venue=P.get('venue'), year=P.get('year')), dict(venue=P.get('venue'))]:
            rows=backend.find_events(**{k:v for k,v in relax.items() if v})
            if rows:
                st.log("self_correct", strategy="relaxed_date", params=relax, result=rows[0].get('gold'))
                st.turns+=1; st.evidence.append(rows[0]['qid'])
                return rows[0].get('gold') or "", [rows[0]['qid']]
    if plan['op']=="temporal_gold":
        # widen: pick best gender/number-aware event match across that year
        from src.agents.executor import _pick_event
        seas=P.get('season')
        years=[y for y in backend.games_years(seas) if (y<P['pivot_year'] if P['direction']=='before' else y>P['pivot_year'])]
        if years:
            target=max(years) if P['direction']=='before' else min(years)
            rows=backend.find_events(sport=P.get('sport'), year=target, season=seas)
            best=_pick_event(rows, P.get('event_contains'))
            if best:
                st.log("self_correct", strategy="event_rematch", n=len(rows))
                st.turns+=1; st.evidence.append(best['qid'])
                return best.get('gold') or "", [best['qid']]
    # last resort: vector retrieval + reader
    if retriever is not None:
        hits=retriever.search(question, k=5)
        st.tok += est(sum(len(h['text'][:1200]) for h in hits))
        ans=infobox_reader(question, hits)
        st.log("self_correct", strategy="vector_fallback", docs=[h['doc_id'] for h in hits], result=ans)
        st.turns+=1; st.evidence+=[h['doc_id'] for h in hits]
        return ans, [h['doc_id'] for h in hits]
    return "", []

def _verify(answer, ev, backend, retriever, question, st):
    """Cross-source: does vector retrieval independently support the graph answer?"""
    hits=retriever.search(question, k=5)
    st.tok += est(sum(len(h['text'][:1200]) for h in hits))
    vec_ans=infobox_reader(question, hits)
    agree = norm(answer)==norm(vec_ans) or (vec_ans and norm(vec_ans) in norm(answer)) or (answer and norm(answer) in norm(vec_ans))
    # or: the graph evidence doc appears in the vector top-k (source agreement)
    doc_agree = any(d in ev for d in [h['doc_id'] for h in hits])
    st.log("verify", vector_answer=vec_ans, agree=bool(agree), doc_overlap=bool(doc_agree))
    st.turns+=1
    if agree and doc_agree: return 0.95
    if agree or doc_agree: return 0.8
    # graph compute is authoritative for temporal (deterministic year logic);
    # vector disagreement here usually means RAG picked the wrong edition.
    if st.trace and any(t.get('action')=='graph_execute' and t.get('evidence_docs') for t in st.trace):
        return 0.7
    return 0.5
