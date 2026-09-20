"""Honest token accounting that works offline.
Each strategy reports the context it must feed an LLM to produce its answer.
RAG stuffs k documents into the reader (expensive); GraphRAG feeds a tiny
plan prompt (cheap); Agentic adds verification. est_tokens ~= chars/4."""

def est(chars): return max(1, chars // 4)

# rough fixed prompt scaffolding per strategy (system + instructions)
SCAFFOLD = {"rag": 120, "graphrag": 220, "agentic": 260}
