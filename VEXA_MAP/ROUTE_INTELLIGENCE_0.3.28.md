# VEXA Route Intelligence 0.3.28 — directed turn restrictions

- `OfflineGraph.findRoute(..., forbiddenTurns=...)` now runs edge-state Dijkstra so a forbidden `(from,via,to)` transition is never traversed. Default empty set keeps old call sites compatible.
- `prepare_offline_navigation.py --turns turns.csv` optionally installs `vexa_turn_restrictions` into the MBTiles SQLite file; each restriction is checked against existing directed arcs. All inserts are transactional. With `--turns`, schema metadata is v2; otherwise legacy v1.
- CSV columns: `from_id,via_id,to_id`; identifiers refer to directed road nodes, not OSM way IDs. The upstream converter must resolve OSM turn relations to node transitions; restrictions with via ways, conditional restrictions and complex junctions are **not** covered by this representation.
- This change does not automatically wire restrictions into Android's SQLite reader: next integration step must read `vexa_turn_restrictions` and pass the set into the route call; without that integration the installed restrictions are not enforced at runtime.
- Real Moscow/oblast road data and road tests not included. No VPS, GitHub or production modifications.
