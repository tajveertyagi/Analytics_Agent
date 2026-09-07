# Sarthi — DISCOM Analytics Chatbot

A production-style chatbot for an Indian power distribution company (DISCOM):
FastAPI backend (streaming OpenAI tool-calling, SQLite-persisted chat
sessions, in-process caching) + a React chat UI with per-browser sessions
(anonymous, ChatGPT-guest-style) and inline Plotly charts.

- **Transformer/distribution losses** — **real production data**: 9 monthly
  DT-level energy-audit reports (Feb–Oct 2025) consolidated from
  `Production_Data/`.
- **Theft case booking history** — **synthetic placeholder data**, sampled
  onto the real Division/Feeder names, until a real theft dataset is provided.

The app clearly labels which numbers are real and which are synthetic, both
in tool descriptions (so the assistant says so) and passively in the UI.

## Architecture

```
backend/            FastAPI app (Python)
  app/
    main.py            App entrypoint, CORS, startup cache warm
    config.py           Env config
    db.py / models.py    SQLite via SQLAlchemy: users, chat_sessions, chat_messages
    deps.py               Anonymous per-browser identity (uid cookie)
    data_cache.py          In-process cache for the two DataFrames (Parquet-backed)
    analytics.py            Pure pandas KPI/aggregation functions
    charts.py                 Plotly figure builders
    chatbot/
      tools.py                 LLM tool schemas + dispatcher, TTL-cached
      agent.py                  Streaming OpenAI tool-calling loop
    routers/
      sessions.py                Session/message CRUD
      chat.py                     SSE streaming chat endpoint
  requirements.txt

frontend/            React + TypeScript + Vite + Tailwind
  src/
    api.ts              fetch wrappers + SSE parser
    App.tsx               Layout: Sidebar + ChatWindow
    hooks/useChat.ts        Streaming chat state
    components/              Sidebar, ChatWindow, MessageBubble, ChartRenderer, ChatInput

scripts/              Data ingestion (unchanged by the FastAPI/React rebuild)
  build_transformer_losses.py   Consolidates Production_Data/*.xlsx -> data/transformer_losses.xlsx
  generate_sample_data.py        Synthetic theft_cases.xlsx, sampled onto real feeders

data/                 transformer_losses.xlsx, theft_cases.xlsx (+ .parquet cache, gitignored)
Production_Data/      Raw monthly source Excel files (gitignored)
```

## Setup

```bash
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use venv\Scripts\Activate.ps1 in PowerShell
pip install -r requirements.txt -r backend/requirements.txt

cp .env.example .env           # then edit .env and add your OPENAI_API_KEY
```

## Build the data

1. Real transformer-loss data: place the monthly "DT EA Report" Excel files
   in `Production_Data/`, then:
   ```bash
   python scripts/build_transformer_losses.py
   ```
   Consolidates them into `data/transformer_losses.xlsx`, normalizing
   column-name/casing inconsistencies, converting loss fractions to
   percentages, and flagging data-quality issues (`Data_Quality_Flag`: `OK` /
   `Outlier` — implausible % from a near-zero denominator / `Unbilled` — no
   consumer meter reading captured that month). Aggregate KPIs/tools exclude
   `Outlier`/`Unbilled` rows by default.

2. Synthetic theft data (run after step 1 — it samples real feeder names):
   ```bash
   python scripts/generate_sample_data.py
   ```

To use a **real** theft dataset instead, replace `data/theft_cases.xlsx`
keeping the same columns, and update the "synthetic" language in
`backend/app/chatbot/agent.py`'s system prompt and `backend/app/chatbot/tools.py`'s
tool descriptions.

## Run

Two processes, in separate terminals:

```bash
# Terminal 1 -- backend (from backend/, so `app.*` imports resolve)
cd backend
source ../venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 -- frontend
cd frontend
npm install   # first time only
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`). The Vite dev
server proxies `/api/*` to the backend on port 8000 (see `vite.config.ts`),
so no CORS setup is needed in dev.

First visit: the backend sets an anonymous `vidyutiq_uid` cookie (no login)
and the frontend auto-creates a first chat session. Sessions and messages
persist in `backend/vidyutiq.db` (SQLite) — refreshing the page keeps your
chat history; a different browser/incognito window gets its own empty
session list.

## Caching

- `data_cache.py` caches the two reference DataFrames in-process, backed by
  a Parquet sidecar (`data/*.parquet`) regenerated whenever the source
  `.xlsx` is newer — avoids the ~30s openpyxl parse of the 37k-row loss file
  on every cold start (subsequent loads are ~1s).
- `chatbot/tools.py::dispatch` is wrapped in a 5-minute TTL cache
  (`cachetools`) keyed by tool name + arguments, so repeated identical
  analytics questions (common across sessions) skip recomputation.

## Verification notes

Ground-truth numbers used to sanity-check the chatbot during development
(from `analytics.loss_by_division`/`loss_by_dt_type` on the current dataset):
highest-loss division **Surajpur-II (27.74%)**, worst transformer type
**Domestic-Rural (45.3%)**. If these drift after re-running the ingestion
scripts with new data, that's expected — just re-derive and don't assume the
old numbers still hold.
