"""GraphRAG: NL -> structured plan -> graph compute -> answer.
LLM only plans (tiny prompt); graph computes. Deterministic & cheap."""
from __future__ import annotations
from src.agents.planner import heuristic_plan, llm_plan
from src.agents.executor import execute
from src.utils.cost import est, SCAFFOLD

def run(question, backend, llm=None, use_llm_planner=False, model=None):
    if use_llm_planner and llm and not getattr(llm,'mock',True):
        plan = llm_plan(llm, question, model); tok = llm.usage.snapshot()['total_tok']
    else:
        plan = heuristic_plan(question); tok = est(len(question)) + SCAFFOLD['graphrag']
    answer, ev = execute(plan, backend)
    return {"answer":answer, "evidence":ev, "plan":plan, "est_tokens":tok,
            "trace":[{"step":"plan","qtype":plan['qtype'],"op":plan['op'],"params":plan['params']},
                     {"step":"graph_execute","result":answer,"evidence_docs":ev}]}
