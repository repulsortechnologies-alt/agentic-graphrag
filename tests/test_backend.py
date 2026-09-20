import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph.backend import get_backend
b = get_backend()
print("sports:", len(b.sports()), "| Summer years:", b.games_years('Summer')[:5], "...")
# pub-001 biathlon 2018 comp>73 -> 5
print("pub-001:", len(b.find_events(sport='Biathlon', year=2018, season='Winter', min_competitors=73)), "want 5")
# pub-003 shooting 2004 comp>37 -> 8
print("pub-003:", len(b.find_events(sport='Shooting', year=2004, season='Summer', min_competitors=37)), "want 8")
# pub-005 venue+date -> Naim
r = b.find_events(venue='Weightlifting Gymnasium', date_iso='1988-09-20')
print("pub-005:", [e['gold'] for e in r], "want Naim Suleymanoglu")
# superlative pub-004 athletics 2008 max comp -> marathon
ath = b.find_events(sport='Athletics', year=2008, season='Summer')
top = max(ath, key=lambda e:e['competitors'] or 0)
print("pub-004:", top['event'], "want Men's marathon")
