# QueryPilot: notes for Claude Code

Text-to-SQL agent: FastAPI backend (backend/) + React/Vite frontend (frontend/). SQLite demo DB, OpenAI for SQL generation.

## Commands (run backend ones from backend/)
- Install: `pip install -r requirements.txt`
- Build demo DB: `python -m data.seed` (loads data/raw/*.csv, the Maven Analytics Pizza Place Sales dataset, into data/shop.db)
- Run API: `uvicorn app.main:app --reload` (port 8000, docs at /docs)
- Tests: `pytest -q` (no API key needed; tests use FakeLLM from tests/conftest.py)
- Eval: `python -m evals.run_eval [--model gpt-4o] [--only id1,id2] [--repeat N]` (needs OPENAI_API_KEY; costs tokens). Reports go to evals/results/ and include each answer's explanation; --repeat N aggregates mean/min/max accuracy and per-question pass counts. Scoring/summary logic is in run_once / summarize_run / summarize_repeats (tested in tests/test_run_eval.py).
- Eval in Docker: `docker compose build backend && docker compose run --rm backend python -m evals.run_eval --repeat 3`. Only backend/app and backend/evals/results are mounted, so rebuild after changing eval code or seed.py.
- Frontend: `cd frontend && npm install && npm run dev` (port 5173, proxies /api to 8000)
- Both at once: `docker compose up` from the repo root (needs backend/.env). Backend mounts ./backend/app with uvicorn --reload, and ./backend/evals/results so eval reports reach the host; frontend mounts ./frontend with Vite polling. vite.config.js reads API_PROXY_TARGET (http://backend:8000 in compose). Rebuild with --build after dependency or data changes.

## Architecture
- `app/agent.py` TextToSQLAgent.ask(): build prompt with schema → LLM → parse JSON → guard → db.run → on GuardError/QueryError/LLMOutputError append error and retry, up to max_attempts. Returns AgentResult (status ok | unanswerable | failed).
- `app/guard.py` validate_and_limit(): sqlglot parse, single statement, must be exp.Query, forbid writes/PRAGMA/ATTACH, cap LIMIT at max_rows+1.
- `app/db.py` Database: opens SQLite with mode=ro + PRAGMA query_only; progress handler enforces the timeout; fetches max_rows+1 to set `truncated`.
- `app/llm.py` LLMClient protocol + OpenAIClient: `complete(messages, json=True)`; json=False is used for the plain-text answer. parse_llm_json tolerates code fences. Don't name a local variable `json` in modules that use the json module (the parameter already shadows it inside complete).
- After a successful query, if `summarize=True` (on in the app via SUMMARIZE env, off in tests and evals by default), `_add_answer` makes a second call with SUMMARY_PROMPT and the first 50 rows to fill `AgentResult.answer`. It is best effort: failures are logged and the result still returns.
- `frontend/src/lib/format.js` turns raw values into readable ones (column names, months, dates, money, percents, hours). Table and chart both use it.
- Schema docs live as `--` comments inside the CREATE TABLE statements in data/seed.py; SQLite keeps them and they go into the prompt. Comments outside CREATE TABLE are lost.
- Business glossary: data/glossary.md, loaded by `load_glossary()` in app/agent.py and placed in SYSTEM_PROMPT as a "Business definitions" section right after the schema (GLOSSARY_SECTION in prompts.py). `<!-- -->` comments in it are stripped. A missing file logs a warning and the section is left out; the agent still works.
- What goes where: schema comments = facts about columns and rows (formats, allowed values, what a row means, what is absent, SQLite how-tos like strftime). Glossary = what people's words mean in terms of the schema ("pizza" = pizza type, "sold" = SUM(quantity), "revenue"). Don't say the same thing in both. Changing the glossary needs no reseed, but the Docker image must be rebuilt (data/ is baked in).
- Dataset "today" is 2015-12-31 (DATASET_TODAY in agent.py); all orders are in 2015.
- The loader converts dates from dd/mm/yyyy to ISO, zero-pads times, and reads pizza_types.csv as cp1252. tests/test_db.py checks all three and that total revenue is 817860.05.

## Conventions
- Every behavior change gets a pytest test; use FakeLLM to script model replies, never call the real API in tests.
- If you change seed.py, rerun the seed and `pytest tests/test_evals.py` (every gold query must still return rows), and update hardcoded counts in tests.
- Fix eval failures in the product (SYSTEM_PROMPT, schema comments, glossary), never by editing questions.json or gold_sql. Schema notes and glossary entries should be general, not hints for specific questions. Report strict and lenient accuracy as --repeat means.
- Eval questions must have exactly one correct answer: say what to return ("by revenue", "and how many"), and check top-1 questions for ties.
- Keep the guard and the read-only connection both in place; they are deliberate defense in depth.
- Frontend: React Router with two pages, `/` (pages/Landing.jsx) and `/app` (pages/Workspace.jsx). Copy and suggested questions live in src/content.js. Question history is saved in localStorage (src/lib/history.js).
- Frontend style: clean product tool. White/gray, near-black buttons, Schibsted Grotesk for text, IBM Plex Mono only for real SQL/table names. Color is reserved for the highlighter pairs (--hl-*) that link question phrases to SQL. No UI libraries, no all-caps labels, no generic card grids.
- vercel.json rewrites all paths to index.html so /app works on refresh.
