"""Produce answers.jsonl for the 50 hidden questions using the Agentic pipeline."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph.backend import get_backend
from src.pipelines.retriever import TfidfRetriever
from src.pipelines import agentic
from src.utils.llm import LLM, CHEAP
DATA='/home/claude/dataset/hackathon-resources'
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

b=get_backend(); r=TfidfRetriever(f'{DATA}/corpus/corpus.jsonl'); llm=LLM()
hidden=[json.loads(l) for l in open(f'{DATA}/questions/eval_hidden.jsonl')]
out=[]
for q in hidden:
    res=agentic.run(q['question'], b, r, llm, False, CHEAP)
    out.append({"qid":q['qid'],"question":q['question'],"qtype":q['qtype'],
                "answer":[res['answer']],"evidence_doc_ids":res['evidence'],
                "confidence":res['confidence'],"gaps":res['gaps']})
os.makedirs(f'{ROOT}/data/results', exist_ok=True)
with open(f'{ROOT}/data/results/answers_hidden.jsonl','w') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False)+'\n')
# coverage report (no gold, but flag empties/low-confidence)
empty=sum(1 for o in out if not o['answer'][0])
lowc=sum(1 for o in out if o['confidence']<0.6)
from collections import Counter
qt=Counter(o['qtype'] for o in out)
print(f"predicted {len(out)} hidden | empty={empty} low_conf={lowc}")
print("by type:", dict(qt))
print("sample:")
for o in out[:5]: print(f"  {o['qid']} [{o['qtype']}] -> {o['answer'][0][:40]!r} (conf {o['confidence']})")
