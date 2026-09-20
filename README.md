# Agentic GraphRAG — TigerGraph Hackathon

**Thesis: the LLM plans, the graph computes.** The agent translates a natural-language
question into a structured graph query; TigerGraph returns a deterministic answer.
This wins **accuracy** on questions RAG can't touch (aggregation, superlative, temporal,
multi-hop) *and* wins **token efficiency** by keeping counting/filtering/max out of the LLM.

## Results (100 public questions, Olympic corpus)

| Pipeline   | Accuracy | Tokens  | lookup | multi_hop | temporal | aggregation | superlative |
|------------|----------|---------|--------|-----------|----------|-------------|-------------|
| RAG        | **18%**  | 157,342 | 37%    | 32%       | 9%       | 0%          | 0%          |
| GraphRAG   | **92%**  | 24,669  | 100%   | 71%       | 100%     | 100%        | 100%        |
| Agentic    | **100%** | 129,540 | 100%   | 100%      | 100%     | 100%        | 100%        |

- **RAG** is expensive *and* wrong: top-k retrieval can't pull the 40+ docs needed to count,
  and TF-IDF picks the wrong Olympic edition for "immediately before 2016".
- **GraphRAG** pushes the work into the graph: 5× cheaper, 5× more accurate.
- **Agentic** spends extra tokens on cross-source verification and venue+date
  disambiguation to close the last 8 points — exactly the multi-hop cases where a
  venue hosts many events and GraphRAG grabs the wrong one.

## Architecture

```
Question
   │
   ▼
Planner  ──────────►  structured plan {qtype, op, params}   (LLM plans; heuristic fallback)
   │
   ▼
Orchestrator (agentic loop)
   ├─ 1 plan          decompose question into graph ops
   ├─ 2 graph_execute run op on TigerGraph (count / argmax / filter / venue-date join)
   ├─ 2b refine       multi_hop: disambiguate venue+date collisions (date string + vector tiebreak)
   ├─ 3 judge         is the evidence grounded / sufficient?
   ├─ 4 self_correct  relax constraints, re-match event, or fall back to vector
   ├─ 5 verify        cross-check single-fact answers against vector retrieval
   └─ 6 stop          confidence-based stopping
   │
   ▼
answer + evidence doc_ids + full investigation trace + confidence
```

Three pipelines share components so the benchmark is apples-to-apples:
- **RAG** = `retriever` (TF-IDF / TigerGraph Vector) → `reader`.
- **GraphRAG** = `planner` → `executor` (graph compute). No investigation.
- **Agentic** = `orchestrator` over the same executor + retriever, with judge/refine/verify/stop.

## Backends (swap with one env var)
- `GRAPH_BACKEND=local` — in-memory over `data/events.jsonl`. Instant, deterministic, zero setup. Default.
- `GRAPH_BACKEND=tigergraph` — Savanna via installed GSQL queries over RESTPP (`src/graph/queries.gsql`).

## Run

```bash
pip install -r requirements.txt

# 1. build graph data from the corpus (already committed, but to regenerate:)
python3 src/graph/extract.py <corpus.jsonl> data/events.jsonl
python3 scripts/gen_csv.py

# 2. benchmark all three pipelines (offline, no API key needed)
python3 scripts/benchmark.py

# 3. metrics dashboard -> dashboard/index.html
python3 scripts/make_dashboard.py

# 4. predictions for the hidden set -> data/results/answers_hidden.jsonl
python3 scripts/predict_hidden.py

# 5. live demo
streamlit run dashboard/app.py
```

Set `GEMINI_API_KEY` (free tier) to use the LLM planner/reader; otherwise the system
runs fully deterministic (heuristic planner + infobox reader) and still scores as above.

## TigerGraph Savanna setup
1. Sign up at tgcloud.io, redeem hackathon credits, create a workspace (port 443).
2. Admin Portal → User Management → generate a **secret**.
3. Load schema + data:
   ```
   gsql src/graph/schema.gsql
   # upload data/*.csv, then:
   gsql src/graph/load.gsql          # runs load_all + load_medals
   gsql src/graph/queries.gsql
   gsql -g olympics "INSTALL QUERY ALL"
   ```
4. `cp .env.example .env`, set `GRAPH_BACKEND=tigergraph`, `TG_HOST`, `TG_SECRET`.

## Data
2,951 corpus docs → **2,187 Olympic events** extracted from Wikipedia infoboxes
(99% infobox coverage, 97% dates parsed). **764 distractor docs** (films, companies)
are excluded from the graph — RAG can be misled by them, the graph can't.
Graph: 2,187 events, 6,085 athletes, 319 venues, 21 games, 42 sports.

## Layout
```
src/graph/     extract.py  backend.py  schema.gsql  load.gsql  queries.gsql
src/agents/    planner.py  executor.py  orchestrator.py
src/pipelines/ rag.py  graphrag.py  agentic.py  retriever.py  reader.py
src/utils/     llm.py  cost.py
scripts/       benchmark.py  predict_hidden.py  make_dashboard.py  gen_csv.py
dashboard/     index.html (static)  app.py (streamlit)
tests/         test_backend.py  test_pipelines.py
```
