"""Document retrieval. TfidfRetriever = offline stand-in for TigerGraph Vector DB.
Swap to TigerGraph Vector via same .search() signature at submission.
Includes distractor docs (films/companies) on purpose -> RAG can be misled."""
from __future__ import annotations
import json, os, re, pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class TfidfRetriever:
    def __init__(self, corpus_path, cache=None):
        self.docs=[]; self.ids=[]; self.titles=[]; self.texts=[]
        for line in open(corpus_path):
            d=json.loads(line)
            self.docs.append(d); self.ids.append(d['doc_id'])
            self.titles.append(d['title']); self.texts.append(d['title']+"\n"+d['text'])
        self.by_id={d['doc_id']:d for d in self.docs}
        cache = cache or corpus_path+'.tfidf.pkl'
        if os.path.exists(cache):
            self.vec, self.mat = pickle.load(open(cache,'rb'))
        else:
            self.vec = TfidfVectorizer(max_features=50000, ngram_range=(1,2), stop_words='english', sublinear_tf=True)
            self.mat = self.vec.fit_transform(self.texts)
            pickle.dump((self.vec,self.mat), open(cache,'wb'))

    def search(self, query, k=5):
        q = self.vec.transform([query])
        scores = (self.mat @ q.T).toarray().ravel()
        idx = np.argsort(-scores)[:k]
        return [{"doc_id":self.ids[i],"title":self.titles[i],
                 "text":self.by_id[self.ids[i]]['text'],"score":float(scores[i])} for i in idx]

    def get(self, doc_id): return self.by_id.get(doc_id)
