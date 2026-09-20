import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph.backend import get_backend, norm
from src.pipelines.retriever import TfidfRetriever
from src.pipelines import rag, graphrag, agentic
DATA=os.getenv('DATA','/home/claude/dataset/hackathon-resources')

def _m(a,g): a=norm(a); return any(norm(x)==a or norm(x) in a for x in g)

def test_all():
    b=get_backend(); r=TfidfRetriever(f'{DATA}/corpus/corpus.jsonl')
    pub=[json.loads(l) for l in open(f'{DATA}/questions/eval_public.jsonl')]
    ag=sum(_m(agentic.run(q['question'],b,r)['answer'], q['answer']) for q in pub)
    gr=sum(_m(graphrag.run(q['question'],b)['answer'], q['answer']) for q in pub)
    assert ag>=95, f"agentic regressed: {ag}/100"
    assert gr>=88, f"graphrag regressed: {gr}/100"
    print(f"OK agentic={ag}/100 graphrag={gr}/100")

if __name__=='__main__': test_all()
