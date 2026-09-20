"""Run RAG / GraphRAG / Agentic on the public set, score accuracy + completeness + tokens."""
import sys, os, json, re, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph.backend import get_backend, norm
from src.pipelines.retriever import TfidfRetriever
from src.pipelines import rag, graphrag, agentic
from src.utils.llm import LLM, CHEAP, STRONG

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA='/home/claude/dataset/hackathon-resources'

def match(pred, gold_list):
    p=norm(pred)
    if not p: return False
    for g in gold_list:
        gn=norm(g)
        if p==gn or gn in p or p in gn: return True
        # numeric compare
        pm=re.search(r'-?\d+',p); gm=re.search(r'-?\d+',gn)
        if pm and gm and pm.group()==gm.group(): return True
    return False

def doc_recall(ev, gold_docs):
    if not gold_docs: return 1.0
    return len(set(ev)&set(gold_docs))/len(set(gold_docs))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--llm-planner', action='store_true')
    args=ap.parse_args()

    backend=get_backend()
    retr=TfidfRetriever(f'{DATA}/corpus/corpus.jsonl')
    llm=LLM()  # mock unless GEMINI_API_KEY set
    print(f"LLM mock={llm.mock} | planner={'LLM' if args.llm_planner else 'heuristic'}")

    pub=[json.loads(l) for l in open(f'{DATA}/questions/eval_public.jsonl')][:args.n]
    rows=[]
    t0=time.time()
    for i,q in enumerate(pub):
        gold=q['answer']; gd=q['gold_doc_ids']; qt=q['qtype']
        llm.usage.reset(); r_rag=rag.run(q['question'], retr, llm, model=STRONG); u_rag={"total_tok":r_rag.get("est_tokens",0)}
        llm.usage.reset(); r_gr=graphrag.run(q['question'], backend, llm, args.llm_planner, CHEAP); u_gr={"total_tok":r_gr.get("est_tokens",0)}
        llm.usage.reset(); r_ag=agentic.run(q['question'], backend, retr, llm, args.llm_planner, CHEAP); u_ag={"total_tok":r_ag.get("est_tokens",0)}
        rows.append({
            "qid":q['qid'],"qtype":qt,"question":q['question'],"gold":gold,
            "rag":{"answer":r_rag['answer'],"correct":match(r_rag['answer'],gold),"recall":doc_recall(r_rag['evidence'],gd),"tokens":u_rag['total_tok']},
            "graphrag":{"answer":r_gr['answer'],"correct":match(r_gr['answer'],gold),"recall":doc_recall(r_gr['evidence'],gd),"tokens":u_gr['total_tok']},
            "agentic":{"answer":r_ag['answer'],"correct":match(r_ag['answer'],gold),"recall":doc_recall(r_ag['evidence'],gd),"tokens":u_ag['total_tok'],"confidence":r_ag.get('confidence')},
        })
        if (i+1)%25==0: print(f"  {i+1}/{len(pub)} ...")
    os.makedirs(f'{ROOT}/data/results', exist_ok=True)
    json.dump(rows, open(f'{ROOT}/data/results/benchmark.json','w'), indent=1, ensure_ascii=False)

    # summary
    from collections import defaultdict
    def agg(key):
        acc=defaultdict(lambda:[0,0]); tok=defaultdict(int); rec=defaultdict(float)
        for r in rows:
            c=r[key]; qt=r['qtype']
            acc[qt][0]+=c['correct']; acc[qt][1]+=1
            acc['ALL'][0]+=c['correct']; acc['ALL'][1]+=1
            tok[qt]+=c['tokens']; tok['ALL']+=c['tokens']
            rec[qt]+=c['recall']; rec['ALL']+=c['recall']
        return acc,tok,rec
    print(f"\n{'qtype':12} {'RAG':>14} {'GraphRAG':>14} {'Agentic':>14}")
    order=['lookup','multi_hop','temporal','aggregation','superlative','ALL']
    A={k:agg(k) for k in ('rag','graphrag','agentic')}
    for qt in order:
        cells=[]
        for k in ('rag','graphrag','agentic'):
            acc,tok,rec=A[k]
            n=acc[qt][1] or 1
            cells.append(f"{acc[qt][0]}/{acc[qt][1]} ({100*acc[qt][0]//n}%)")
        print(f"{qt:12} {cells[0]:>14} {cells[1]:>14} {cells[2]:>14}")
    print(f"\nTotal tokens:")
    for k in ('rag','graphrag','agentic'):
        _,tok,_=A[k]; print(f"  {k:10}: {tok['ALL']:>8} tok")
    print(f"\nElapsed {time.time()-t0:.1f}s -> data/results/benchmark.json")

if __name__=='__main__': main()
