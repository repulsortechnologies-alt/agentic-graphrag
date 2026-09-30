# Evaluation Results

## Visible set — 100 questions (with gold answers)

| Pipeline | Accuracy | Tokens | lookup | multi_hop | temporal | aggregation | superlative |
|---|---|---|---|---|---|---|---|
| rag | 18.0% | 157,342 | 36.8% | 32.1% | 9.1% | 0.0% | 0.0% |
| graphrag | 92.0% | 24,669 | 100.0% | 71.4% | 100.0% | 100.0% | 100.0% |
| agentic | 100.0% | 129,540 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

- **RAG** is expensive and wrong: top-k retrieval can't pull the many docs needed to count, and picks the wrong Olympic edition for "before 2016".
- **GraphRAG** pushes counting/filtering/superlatives into the graph — 5x cheaper, 5x more accurate.
- **Agentic** adds cross-source verification + venue/date disambiguation, closing the last points on multi-hop.

Raw per-question output: [`data/results/benchmark.json`](data/results/benchmark.json)
Machine summary: [`data/results/summary.json`](data/results/summary.json)

## Hidden set — 50 questions (no gold; predictions submitted)

Predictions produced by the Agentic pipeline for all 50 hidden questions:
[`data/results/answers_hidden.jsonl`](data/results/answers_hidden.jsonl)

By type: {'multi_hop': 10, 'lookup': 7, 'aggregation': 15, 'superlative': 10, 'temporal': 8}
Coverage: 50/50 answered (0 empty).

Reproduce:
```
python3 scripts/benchmark.py        # visible 100 -> benchmark.json + summary
python3 scripts/predict_hidden.py   # hidden 50  -> answers_hidden.jsonl
python3 scripts/make_dashboard.py   # -> dashboard/index.html
```
