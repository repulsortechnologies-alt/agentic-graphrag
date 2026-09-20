"""LLM client. Gemini (free tier) with disk cache + backoff + model routing.
MockLLM lets the whole system run offline with zero API calls.
Every call records token usage so the benchmark can measure efficiency.
"""
from __future__ import annotations
import os, json, time, hashlib, random

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.llmcache')
os.makedirs(CACHE_DIR, exist_ok=True)

# model routing: cheap for extraction/routing, strong for reasoning/synthesis
CHEAP = "gemini-2.5-flash-lite"
STRONG = "gemini-2.5-flash"

def _key(model, prompt, system):
    h = hashlib.sha256(f"{model}||{system}||{prompt}".encode()).hexdigest()[:32]
    return os.path.join(CACHE_DIR, h + ".json")

class Usage:
    def __init__(self): self.calls=0; self.in_tok=0; self.out_tok=0
    def add(self, i, o): self.calls+=1; self.in_tok+=i; self.out_tok+=o
    def snapshot(self): return {"calls":self.calls,"in_tok":self.in_tok,"out_tok":self.out_tok,"total_tok":self.in_tok+self.out_tok}
    def reset(self): self.__init__()

class LLM:
    def __init__(self, api_key=None, mock=None):
        self.usage = Usage()
        self.mock = mock if mock is not None else (os.getenv('LLM_MOCK','0')=='1' or not (api_key or os.getenv('GEMINI_API_KEY')))
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self._client = None

    def _gemini(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def complete(self, prompt, system="", model=CHEAP, temperature=0.0, use_cache=True, json_out=False):
        if use_cache:
            kp = _key(model, prompt, system)
            if os.path.exists(kp):
                d = json.load(open(kp))
                self.usage.add(d.get('in_tok',0), d.get('out_tok',0))
                return d['text']
        if self.mock:
            text = self._mock_response(prompt, system, json_out)
            it, ot = len(prompt)//4, len(text)//4
            self.usage.add(it, ot)
            if use_cache: json.dump({"text":text,"in_tok":it,"out_tok":ot}, open(_key(model,prompt,system),'w'))
            return text
        # real Gemini with backoff on 429
        for attempt in range(6):
            try:
                cfg = {"temperature":temperature}
                if json_out: cfg["response_mime_type"]="application/json"
                full = (system+"\n\n"+prompt) if system else prompt
                r = self._gemini().models.generate_content(model=model, contents=full, config=cfg)
                text = r.text or ""
                um = getattr(r,'usage_metadata',None)
                it = getattr(um,'prompt_token_count',len(full)//4) if um else len(full)//4
                ot = getattr(um,'candidates_token_count',len(text)//4) if um else len(text)//4
                self.usage.add(it, ot)
                if use_cache: json.dump({"text":text,"in_tok":it,"out_tok":ot}, open(_key(model,prompt,system),'w'))
                return text
            except Exception as ex:
                if '429' in str(ex) or 'RESOURCE_EXHAUSTED' in str(ex):
                    time.sleep(min(2**attempt + random.random(), 60)); continue
                raise
        raise RuntimeError("Gemini rate-limit: exhausted retries")

    def _mock_response(self, prompt, system, json_out):
        """Deterministic stand-in so pipelines run/validate offline.
        Recognizes the structured prompts our agents send."""
        p = prompt.lower()
        if json_out or 'return json' in (system+prompt).lower():
            if 'classify' in p or 'qtype' in p:
                for t in ('aggregation','superlative','temporal','multi_hop','lookup'):
                    if t.replace('_',' ') in p or t in p: return json.dumps({"qtype":t})
                return json.dumps({"qtype":"lookup"})
            return json.dumps({"note":"mock"})
        return "MOCK_ANSWER"
