"""Graph backend abstraction.
LocalBackend: in-memory over events.jsonl (offline dev, instant).
TigerGraphBackend: REST calls to Savanna (submission).
Same query interface -> pipelines are backend-agnostic.
"""
from __future__ import annotations
import json, os, re, unicodedata
from abc import ABC, abstractmethod

def norm(s: str) -> str:
    if not s: return ""
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode()
    return re.sub(r'\s+',' ', s.lower().strip())

class GraphBackend(ABC):
    @abstractmethod
    def find_events(self, sport=None, year=None, season=None, venue=None,
                    date_iso=None, min_competitors=None, max_competitors=None,
                    min_nations=None, event_contains=None, athlete=None) -> list[dict]: ...
    @abstractmethod
    def get_event(self, qid: str) -> dict | None: ...
    @abstractmethod
    def sports(self) -> list[str]: ...
    @abstractmethod
    def games_years(self, season=None) -> list[int]: ...

class LocalBackend(GraphBackend):
    def __init__(self, events_path):
        self.events = [json.loads(l) for l in open(events_path)]
        self.by_qid = {e['qid']: e for e in self.events}
        self._sports = sorted({e['sport'] for e in self.events if e['sport']})
        self._sport_norm = {norm(s): s for s in self._sports}

    def _match_sport(self, sport):
        if not sport: return None
        n = norm(sport)
        if n in self._sport_norm: return self._sport_norm[n]
        for k,v in self._sport_norm.items():
            if n in k or k in n: return v
        return sport

    def find_events(self, sport=None, year=None, season=None, venue=None,
                    date_iso=None, min_competitors=None, max_competitors=None,
                    min_nations=None, event_contains=None, athlete=None):
        s = self._match_sport(sport) if sport else None
        vn = norm(venue) if venue else None
        ec = norm(event_contains) if event_contains else None
        an = norm(athlete) if athlete else None
        out=[]
        for e in self.events:
            if s and e['sport']!=s: continue
            if year and e['year']!=year: continue
            if season and e['season']!=season: continue
            if vn and vn not in norm(e['venue']): continue
            if date_iso and e['date_iso']!=date_iso: continue
            c = e['competitors'] or 0
            if min_competitors is not None and not (c>min_competitors): continue
            if max_competitors is not None and not (c<max_competitors): continue
            if min_nations is not None and not ((e['nations'] or 0)>min_nations): continue
            if ec and ec not in norm(e['event']): continue
            if an and an not in (norm(e['gold'])+' '+norm(e['silver'])+' '+norm(e['bronze'])): continue
            out.append(e)
        return out

    def get_event(self, qid): return self.by_qid.get(qid)
    def sports(self): return self._sports
    def games_years(self, season=None):
        return sorted({e['year'] for e in self.events if e['year'] and (not season or e['season']==season)})

class TigerGraphBackend(GraphBackend):
    """Savanna via installed GSQL queries exposed as REST. Env: TG_HOST, TG_GRAPH, TG_TOKEN or TG_SECRET."""
    def __init__(self, host=None, graph=None, token=None, secret=None):
        import httpx
        self.host = (host or os.getenv('TG_HOST','')).rstrip('/')
        self.graph = graph or os.getenv('TG_GRAPH','olympics')
        self.token = token or os.getenv('TG_TOKEN')
        self._secret = secret or os.getenv('TG_SECRET')
        self._c = httpx.Client(timeout=30.0)
        if not self.token and self._secret:
            self.token = self._mint_token()

    def _mint_token(self):
        r = self._c.post(f"{self.host}/restpp/requesttoken",
                         json={"secret": self._secret, "lifetime": 86400})
        return r.json().get("token")

    def _run(self, endpoint, params):
        h = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        r = self._c.get(f"{self.host}/restpp/query/{self.graph}/{endpoint}", params=params, headers=h)
        r.raise_for_status()
        return r.json().get("results", [])

    def find_events(self, **kw):
        params = {k:v for k,v in kw.items() if v is not None}
        res = self._run("findEvents", params)
        return res[0].get("events", res[0]) if res else []
    def get_event(self, qid):
        res = self._run("getEvent", {"qid": qid})
        return (res[0].get("event") or [None])[0] if res else None
    def sports(self):
        res = self._run("listSports", {}); return res[0].get("sports", []) if res else []
    def games_years(self, season=None):
        res = self._run("gamesYears", {"season": season} if season else {})
        return res[0].get("years", []) if res else []

def get_backend():
    if os.getenv('GRAPH_BACKEND','local').lower() == 'tigergraph':
        return TigerGraphBackend()
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return LocalBackend(os.path.join(root,'data','events.jsonl'))
