# Running on TigerGraph Savanna (verified)

The graph backend runs on a TigerGraph Savanna workspace. Steps that were used
to bring it up end-to-end:

## 1. Workspace
- Create a workspace at tgcloud.io (Savanna). Note the host, e.g.
  `https://<id>.i.tgcloud.io` (REST is on port **443**).
- Advanced Settings → turn **Auto Resume ON** (so REST calls wake a suspended
  workspace instead of returning HTTP 500 "Auto start is not enabled").

## 2. Schema + query endpoints
GraphStudio → Query Editor → paste and run `src/graph/savanna_setup.gsql`.
Creates the `olympics` graph, the `Event` vertex (denormalized: medals stored as
attributes), and installs `findEvents`, `getEvent`, `listSports`, `gamesYears`.

## 3. Auth
Admin Portal → Database Secrets → **Create Secret**, copy the value.
TigerGraph 4.x mints REST tokens at `POST /gsql/v1/tokens` with
`{"secret": "...", "lifetime": 2592000}` (NOT the older `/restpp/requesttoken`,
which returns 400 here).

## 4. Load data (REST upsert)
macOS system Python's TLS is old, so the loader shells out to `curl`:
```
cd scripts
export TG_HOST=https://<id>.i.tgcloud.io
export TG_SECRET=<your secret>
python3 load_to_tigergraph.py     # upserts 2187 events, verifies findEvents==5
```

## 5. Run against Savanna
```
export GRAPH_BACKEND=tigergraph
python3 scripts/benchmark.py       # same benchmark, computed on TigerGraph
python3 scripts/demo_tg.py         # 5 questions across all types, live on Savanna
```

## Notes / gotchas found the hard way
- Installed-query REST calls need **every** parameter supplied; unfilled ones use
  no-op defaults (`""` / `0`). The backend does this automatically.
- URL-encode spaces as `%20`, not `+` (TigerGraph LIKE won't match `+`).
- findEvents returns TigerGraph vertices `{v_id, attributes:{...}}`; the backend
  flattens them to plain dicts for the shared executor.
