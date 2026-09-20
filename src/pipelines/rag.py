"""RAG: vector/tfidf retrieve top-k docs -> reader extracts answer.
Strong on single-doc lookups, weak on aggregation/temporal/multi-doc."""
from __future__ import annotations
from src.pipelines.reader import infobox_reader, llm_reader
from src.utils.cost import est, SCAFFOLD

def run(question, retriever, llm=None, k=5, model=None):
    hits = retriever.search(question, k=k)
    # reader must ingest the full retrieved context -> that's the token cost
    ctx_chars = sum(len(h['text'][:1200]) for h in hits) + len(question)
    if llm and not getattr(llm, 'mock', True):
        ans = llm_reader(llm, question, hits, model); tok = llm.usage.snapshot()['total_tok']
    else:
        ans = infobox_reader(question, hits); tok = est(ctx_chars) + SCAFFOLD['rag']
    return {"answer":ans, "evidence":[h['doc_id'] for h in hits], "est_tokens":tok,
            "trace":[{"step":"retrieve","docs":[h['doc_id'] for h in hits],"scores":[round(h['score'],3) for h in hits]},
                     {"step":"read","answer":ans,"context_docs":k}]}
