# BusinessMind AI — Intelligent Business Intelligence Platform

A full-stack, AI-powered Business Intelligence SaaS platform. Organizations upload their
datasets (CSV / Excel), get instant KPIs, interactive dashboards, anomaly detection,
ML-based forecasting, a conversational business assistant, and professional PDF reports.
Dataset figures are computed from the uploaded data; general business advice is model-generated
and should be treated as guidance, not verified company facts.

Built entirely with free, open-source technologies (€0 cost).

## Features

| Feature | How it works |
|---|---|
| **AI data analysis** | Automatic profiling, KPIs, trend detection, z-score anomaly detection, correlations (pandas / NumPy) |
| **Conversational business assistant** | Local Ollama chat for general business discussion, follow-ups and adaptive answers; it can call a fixed set of validated, read-only analytics tools |
| **Grounded data analysis** | Dataset profiling, KPI, comparison, trend, correlation, anomaly and forecast tools calculate figures in Python; the model explains those results and never runs code or SQL |
| **Conversation and business memory** | Persistent, per-user conversations; editable organization context; delete conversations or clear context at any time |
| **Interactive dashboards** | Recharts area/donut/bar/line charts, KPI cards, dark & light mode |
| **Business forecasting** | scikit-learn `LinearRegression` with trend + seasonal features, 95% prediction intervals, MAPE quality metric |
| **Automated PDF reports** | reportlab: KPIs, insights, breakdowns, forecasts, anomaly review |
| **Data management** | Upload validation (type, size, parseability), cleaning, per-organization storage |
| **User management** | JWT auth (access + rotating refresh tokens), bcrypt password hashing, roles: admin / analyst / viewer |
| **Multi-tenant** | Every query is scoped by `org_id`; cross-tenant access returns 404 (no existence leakage) |

## Tech stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2
- **AI/ML:** pandas · scikit-learn · Ollama (`llama3.1` by default)
- **Frontend:** React 18 · TypeScript (strict) · Tailwind CSS · Recharts · Vite
- **Database:** PostgreSQL 16
- **Reports:** reportlab
- **Deployment:** Docker + Docker Compose

## Project structure

```
app/
├── Dockerfile              # multi-stage: frontend build → Python runtime
├── docker-compose.yml      # app + PostgreSQL (+ optional Ollama)
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py         # app factory, middleware (CORS, security headers, rate limit)
│   │   ├── config.py       # env-driven settings
│   │   ├── models.py       # Organizations, users, datasets, reports and assistant memory
│   │   ├── security.py     # bcrypt + JWT
│   │   ├── deps.py         # auth guard + RBAC
│   │   ├── routers/        # auth, users, datasets, analytics, assistant, reports
│   │   └── services/       # profiling, analysis, forecasting, assistant agent/tools, llm, reporting
│   ├── tests/              # auth, isolation, uploads, analytics, assistant and security tests
│   └── scripts/generate_sample.py
├── frontend/               # React + TS + Tailwind source
└── sample_data/sample_sales.csv
```

## Run with Docker (recommended)

```bash
cp .env.example .env
# set JWT_SECRET and DB_PASSWORD in .env
docker compose up --build
```

Open http://localhost:8000 — create your organization, upload
`sample_data/sample_sales.csv`, and explore.

### Enable conversational AI with Ollama

Run a local Ollama server and download a model (the default is `llama3.1`). The model
is downloaded to your computer; it is not included with this app.

```bash
# Option A: on your host
ollama pull llama3.1 && ollama serve

# Option B: in Docker
docker compose --profile ollama up -d
docker exec -it <ollama-container> ollama pull llama3.1
# then set OLLAMA_URL=http://ollama:11434 in .env
```

For the Ollama Windows installer, see [Ollama for Windows](https://ollama.com/download/windows).
When running the app directly on Windows, the default `OLLAMA_URL` is
`http://localhost:11434`. With Docker Compose, it defaults to
`http://host.docker.internal:11434`.

The assistant sends prompts, explicitly saved organization context, column
metadata, and requested aggregate tool results to the configured Ollama server.
It does not send raw dataset rows. By default, only common local Ollama hostnames
are allowed. To use a remote Ollama host, set `OLLAMA_URL` and explicitly set
`OLLAMA_ALLOW_REMOTE=true`; only do this for a server you trust. No cloud AI
provider or cloud API key is configured by default. If Ollama is unavailable,
the existing deterministic dataset-question endpoint and analytics screens remain
available; unrestricted chat requires a running model.

## Run on Windows without Docker

Start Ollama and download `llama3.1` if you want conversational AI. Then use two
PowerShell terminals:

```powershell
# Terminal 1 — backend (Python 3.12)
cd C:\path\to\app\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ENV = "development"
$env:JWT_SECRET = (python -c "import secrets; print(secrets.token_hex(32))")
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd C:\path\to\app\frontend
npm ci
npm run dev
```

The development backend uses local SQLite if `DATABASE_URL` is not set, so
PostgreSQL is not required. Open the Vite URL, usually http://localhost:5173.

## Run without Docker (Linux/macOS)

```bash
# Backend
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg2://businessmind:secret@localhost:5432/businessmind"
export JWT_SECRET="$(openssl rand -hex 32)"
uvicorn app.main:app --reload   # http://localhost:8000

# Frontend
cd frontend
npm ci
npm run dev                     # http://localhost:5173 (proxies /api → :8000)
```

## Tests & security checks

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests/ -q
python -m bandit -r app/          # static security scan
```

Test coverage includes: authentication & refresh-token rotation, password policy,
multi-tenant isolation (cross-org access → 404), RBAC (viewer/analyst/admin),
upload validation (executables, disguised scripts, corrupt files, path traversal),
analytics correctness against ground-truth pandas, SQL-injection probes,
rate limiting, security headers, and error leakage.

### Assistant evaluation methodology

The automated tests use deterministic fixtures and mocked Ollama responses; they
check tool argument validation, exact analytics against known values, refusal of
unregistered operations, report-confirmation gating, tenant/user memory isolation,
conversation summarization, and deterministic behavior when Ollama is offline.
They do not measure a language model's real-world answer quality.

For model evaluation, maintain a versioned set of business questions across
industries, general questions, follow-ups, prompt-injection attempts, and varied
dataset schemas. Record (1) human-rated relevance and factuality, (2) tool-selection
precision/recall against expected tool sets, (3) numerical outputs compared with
independently computed ground truth, (4) privacy/tenant-isolation failures (target
zero), and (5) p50/p95 end-to-end latency. Evaluate each configured model separately,
include Ollama-unavailable cases, and never use production customer data as an
evaluation fixture.

## Security design

- bcrypt password hashing (cost 12), strong password policy
- Short-lived JWT access tokens (30 min) + rotating, single-use refresh tokens (stored as SHA-256 digests)
- Strict RBAC on every endpoint; 404 (not 403) across tenants to avoid existence leaks
- ORM-only queries (no raw SQL), Pydantic input validation everywhere
- Upload allow-list by extension + server-side parse validation + size/row/column limits
- Uploaded files stored under random UUID names inside per-org directories; path-escape guard on every file read
- Security headers (nosniff, frame-deny, referrer policy), CORS allow-list, per-IP rate limiting on credential endpoints
- Generic auth errors, no stack traces in API responses, OpenAPI docs disabled in production
- AI assistant: the model only gets an allow-listed set of validated, read-only analytics tools; it cannot execute Python, SQL, file access or external actions
- Assistant conversations are scoped to both organization and owning user; organization context is separate, editable by analysts/admins, and deletable
- Dataset results sent to Ollama are aggregate outputs and schema metadata, not raw records; remote Ollama is blocked unless explicitly enabled
- Report generation is only proposed by the assistant; the user must confirm before the existing permission-checked report endpoint runs

## Environment variables

See `.env.example`. Key ones: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`,
`OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_ENABLED`, `OLLAMA_ALLOW_REMOTE`,
`OLLAMA_HISTORY_MESSAGES`, `OLLAMA_MAX_TOOL_ROUNDS`, `MAX_UPLOAD_MB`.
