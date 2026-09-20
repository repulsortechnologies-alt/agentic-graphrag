"""Streamlit live-demo: ask a question, watch the agent investigate step by step,
compare RAG vs GraphRAG vs Agentic side by side. Run: streamlit run dashboard/app.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from src.graph.backend import get_backend
from src.pipelines.retriever import TfidfRetriever
from src.pipelines import rag, graphrag, agentic
from src.utils.llm import LLM, CHEAP, STRONG

DATA=os.getenv('DATA','/home/claude/dataset/hackathon-resources')

@st.cache_resource
def load():
    return get_backend(), TfidfRetriever(f'{DATA}/corpus/corpus.jsonl'), LLM()

st.set_page_config(page_title="Agentic GraphRAG", layout="wide")
st.title("Agentic GraphRAG — live investigation")
b, r, llm = load()
st.caption(f"LLM mock={llm.mock} · backend={type(b).__name__}")

examples=[json.loads(l)['question'] for l in open(f'{DATA}/questions/eval_public.jsonl')][:12]
q=st.selectbox("Pick or type a question", examples)
q=st.text_input("Question", q)

if st.button("Investigate", type="primary"):
    c1,c2,c3=st.columns(3)
    with c1:
        st.subheader("RAG")
        res=rag.run(q,r,llm,model=STRONG)
        st.metric("answer", res['answer'] or "—"); st.caption(f"{res['est_tokens']} tok")
        st.json({"retrieved":res['evidence']}, expanded=False)
    with c2:
        st.subheader("GraphRAG")
        res=graphrag.run(q,b,llm,False,CHEAP)
        st.metric("answer", res['answer'] or "—"); st.caption(f"{res['est_tokens']} tok · {res['plan']['qtype']}")
        st.json(res['plan'], expanded=False)
    with c3:
        st.subheader("Agentic")
        res=agentic.run(q,b,r,llm,False,CHEAP)
        st.metric("answer", res['answer'] or "—")
        st.caption(f"{res['est_tokens']} tok · conf {res['confidence']} · {res['turns']} turns")
        st.markdown("**Investigation trace**")
        for t in res['trace']:
            act=t.get('action'); rest={k:v for k,v in t.items() if k not in ('action','turn')}
            st.markdown(f"`{t['turn']}` **{act}** — {rest}")
        if res['gaps']: st.warning("gaps: "+"; ".join(res['gaps']))
