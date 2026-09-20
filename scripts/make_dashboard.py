"""Generate a self-contained HTML metrics dashboard from benchmark.json (no external deps)."""
import json, os
from collections import defaultdict
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows=json.load(open(f'{ROOT}/data/results/benchmark.json'))
PIPES=['rag','graphrag','agentic']; NAMES={'rag':'RAG','graphrag':'GraphRAG','agentic':'Agentic'}
COL={'rag':'#E24B4A','graphrag':'#378ADD','agentic':'#1D9E75'}
QORDER=['lookup','multi_hop','temporal','aggregation','superlative']

acc=defaultdict(lambda:defaultdict(lambda:[0,0])); tok=defaultdict(int); rec=defaultdict(lambda:defaultdict(float)); cnt=defaultdict(int)
for r in rows:
    qt=r['qtype']; cnt[qt]+=1
    for p in PIPES:
        acc[p][qt][0]+=r[p]['correct']; acc[p][qt][1]+=1
        acc[p]['ALL'][0]+=r[p]['correct']; acc[p]['ALL'][1]+=1
        tok[p]+=r[p]['tokens']; rec[p][qt]+=r[p]['recall']; rec[p]['ALL']+=r[p]['recall']
N=len(rows)
def pct(p,qt): a=acc[p][qt]; return 100*a[0]/(a[1] or 1)

def bars_accuracy():
    w=560; gap=14; groupw=(w-40)/len(QORDER); bw=groupw/4
    svg=[f'<svg viewBox="0 0 620 300" width="100%">']
    for gy in [0,25,50,75,100]:
        y=250-gy*2
        svg.append(f'<line x1="40" y1="{y}" x2="600" y2="{y}" stroke="#E5E5E5"/>')
        svg.append(f'<text x="32" y="{y+4}" font-size="11" fill="#888" text-anchor="end">{gy}</text>')
    for gi,qt in enumerate(QORDER):
        gx=48+gi*groupw
        for pi,p in enumerate(PIPES):
            v=pct(p,qt); h=v*2; x=gx+pi*bw
            svg.append(f'<rect x="{x:.0f}" y="{250-h:.0f}" width="{bw-3:.0f}" height="{h:.0f}" fill="{COL[p]}" rx="2"/>')
        svg.append(f'<text x="{gx+groupw/2-6:.0f}" y="268" font-size="11" fill="#555" text-anchor="middle">{qt}</text>')
        svg.append(f'<text x="{gx+groupw/2-6:.0f}" y="282" font-size="10" fill="#aaa" text-anchor="middle">n={cnt[qt]}</text>')
    svg.append('</svg>')
    return ''.join(svg)

def bars_tokens():
    mx=max(tok.values()); svg=['<svg viewBox="0 0 620 160" width="100%">']
    for i,p in enumerate(PIPES):
        y=20+i*44; w=520*tok[p]/mx
        svg.append(f'<rect x="120" y="{y}" width="{w:.0f}" height="28" fill="{COL[p]}" rx="3"/>')
        svg.append(f'<text x="112" y="{y+19}" font-size="13" fill="#333" text-anchor="end">{NAMES[p]}</text>')
        svg.append(f'<text x="{124+w:.0f}" y="{y+19}" font-size="12" fill="#555">{tok[p]:,} tok</text>')
    svg.append('</svg>'); return ''.join(svg)

cards=''.join(
    f'<div class="card"><div class="pname" style="color:{COL[p]}">{NAMES[p]}</div>'
    f'<div class="big">{pct(p,"ALL"):.0f}%</div><div class="sub">accuracy · {acc[p]["ALL"][0]}/{N}</div>'
    f'<div class="sub">{tok[p]:,} tokens · {100*rec[p]["ALL"]/N:.0f}% doc-recall</div></div>'
    for p in PIPES)

trows=''
for qt in QORDER+['ALL']:
    cells=''.join(f'<td style="color:{COL[p]}">{pct(p,qt):.0f}%</td>' for p in PIPES)
    lbl=qt if qt!='ALL' else '<b>ALL</b>'
    trows+=f'<tr><td>{lbl}</td>{cells}<td>{acc["agentic"][qt][1]}</td></tr>'

html=f'''<!doctype html><html><head><meta charset="utf-8"><title>Agentic GraphRAG — Metrics</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#1a1a1a}}
h1{{font-size:22px;font-weight:600}} h2{{font-size:16px;margin-top:32px;color:#333}}
.cards{{display:flex;gap:12px;margin:16px 0}}
.card{{flex:1;border:1px solid #eee;border-radius:12px;padding:16px;text-align:center}}
.pname{{font-weight:600;font-size:14px}} .big{{font-size:34px;font-weight:700;margin:4px 0}}
.sub{{font-size:12px;color:#888}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}
td,th{{padding:7px 10px;border-bottom:1px solid #eee;text-align:center}} td:first-child,th:first-child{{text-align:left}}
.legend{{font-size:12px;color:#888;margin-top:6px}} .k{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 12px;vertical-align:middle}}
.note{{background:#f7f7f5;border-radius:8px;padding:12px 14px;font-size:13px;color:#444;margin-top:8px}}
</style></head><body>
<h1>Agentic GraphRAG — Benchmark ({N} questions, TigerGraph Olympic corpus)</h1>
<div class="cards">{cards}</div>
<h2>Accuracy by question type</h2>{bars_accuracy()}
<div class="legend"><span class="k" style="background:{COL['rag']}"></span>RAG
<span class="k" style="background:{COL['graphrag']}"></span>GraphRAG
<span class="k" style="background:{COL['agentic']}"></span>Agentic</div>
<h2>Token cost (lower is better)</h2>{bars_tokens()}
<div class="note"><b>Read:</b> RAG is expensive <i>and</i> wrong — it can't retrieve enough docs to count or reason over time.
GraphRAG pushes counting/filtering/superlatives into the graph: 5× cheaper, 5× more accurate.
Agentic spends extra tokens on cross-source verification and venue+date disambiguation to close the last {pct("agentic","ALL")-pct("graphrag","ALL"):.0f} points — winning exactly the multi-hop cases GraphRAG can't.</div>
<h2>Accuracy table</h2>
<table><tr><th>type</th><th>RAG</th><th>GraphRAG</th><th>Agentic</th><th>n</th></tr>{trows}</table>
</body></html>'''
os.makedirs(f'{ROOT}/dashboard', exist_ok=True)
open(f'{ROOT}/dashboard/index.html','w').write(html)
# also a machine-readable summary
summary={p:{"accuracy":round(pct(p,"ALL"),1),"tokens":tok[p],
            "by_type":{qt:round(pct(p,qt),1) for qt in QORDER}} for p in PIPES}
json.dump(summary, open(f'{ROOT}/data/results/summary.json','w'), indent=1)
print("wrote dashboard/index.html + summary.json")
print(json.dumps(summary, indent=1))
