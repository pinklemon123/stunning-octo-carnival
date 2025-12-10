# Copilot Instructions for stunning-octo-carnival

Purpose: Equip AI coding agents to be productive quickly in this LLM + Neo4j knowledge graph project.

## Big Picture
- Backend: `backend/app.py` (Flask). Routes: `/api/upload`, `/api/url`, `/api/graph`, `/api/chat`, plus views `/` and `/files`.
- Ingestion: `backend/ingestion.py` parses TXT/MD/PDF/DOCX/PPTX/HTML and scrapes URLs.
- LLM: `langchain-openai.ChatOpenAI` configured for DeepSeek via `DEEPSEEK_*` envs; extraction lives in `run_extraction()`.
- Graph DB: Neo4j via `neo4j` driver. Nodes: label `Entity` with unique `name`. Rels: type `REL` with `predicate`, `confidence`, `source_doc`, `span`.
- Frontend: Jinja templates `backend/templates/*.html` and static assets under `backend/static/` rendering Cytoscape-compatible JSON.
- Architecture overview: see `docs/architecture.md`.

## Environment & Run
- Required envs: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` (see `backend/.env`).
- Install and run (Windows PowerShell):
  ```powershell
  cd e:\creat2\llmgnn\backend
  ..\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python app.py
  ```
- Neo4j optional: app sets `NEO4J_AVAILABLE` and skips DB ops when not reachable.

## Key Patterns
- Extraction prompt returns a pure JSON array of triples; code strips ``` fences before `json.loads`. Keep outputs fence-free.
- Graph API returns Cytoscape-like shape: `{ nodes: [{data:{id,label,...}}], edges: [{data:{id,source,target,label,...}}] }`.
- Cypher ingestion uses `UNWIND $triples` + `MERGE (:Entity{name})` and `MERGE -[:REL{predicate}]->` with properties.
- Subgraph query uses variable-length `r*1..depth`; when `source_doc` is provided with a seed, it applies `ALL(rel IN r WHERE rel.source_doc = $source_doc)`.
- Serialize Neo4j entities/relations via `serialize_neo4j_object()` to avoid non-JSON types.

## Developer Workflow
- Add new parsers in `ingestion.py` by extending `parse_file()` dispatch and implementing `parse_<ext>()` that returns text.
- For new routes, prefer small helpers and reuse `get_subgraph()`/`ingest_triples()`; keep JSON contract consistent with Cytoscape.
- To modify extraction: edit `run_extraction(text, source_doc)`. Maintain the JSON list schema: `subject`, `predicate`, `object`, `confidence`, `span`, plus code-added `source_doc`.
- When Neo4j is offline, return empty graph results instead of errors; mirror current behavior.

## Tests & Debugging
- Active tests: `backend/verify_ingestion.py` (unit tests for parsing) and `backend/test_neo4j.py` (manual DB connectivity/summary).
- LLM connectivity tests (`test_api.py`, `test_llm.py`) and older schema-based extraction test are removed/avoided to prevent external dependency flakiness.
- For LLM-related features, prefer lightweight smoke checks or mock `llm.invoke()` in unit tests.

## Integration Notes
- `langchain-openai` with `model_name="deepseek-chat"` uses `DEEPSEEK_BASE_URL` + `DEEPSEEK_API_KEY`.
- Frontend templates are rendered by `/` and `/files`; data sources are retrieved via `get_source_documents()` (distinct `r.source_doc`).
- Keep graph depth small (default `1`) and cap query results (`LIMIT 100`) to avoid heavy responses.

## Example Extensions
- Add a route to filter graph by `source_doc` only: call `get_subgraph(seed_id=None, depth=1, source_doc=...)` and return JSON.
- Add ingestion from more sources (e.g., CSV): implement `parse_csv(content)` and wire in `parse_file()`.

If any of the above is unclear or misses a pattern you rely on, please comment and we’ll refine this doc.