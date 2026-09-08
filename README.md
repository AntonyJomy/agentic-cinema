# ScriptClear AI

### An AI agent crew that does screenplay E&O clearance research — so Legal starts from evidence, not a blank page.

![Live Demo](https://img.shields.io/badge/demo-Cloud%20Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
![Partner: Parallel](https://img.shields.io/badge/partner-Parallel%20Search%20MCP-111111?style=for-the-badge)
![Built with Google ADK](https://img.shields.io/badge/built%20with-Google%20ADK-4285F4?style=for-the-badge&logo=google&logoColor=white)


|                        |                                                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Live app**           | [https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/](https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/) |
| **Demo video (3 min)** | *← add public YouTube/Vimeo link*                                                                          |
| **Repository**         | [https://github.com/AntonyJomy/agentic-cinema](https://github.com/AntonyJomy/agentic-cinema)               |
| **Partner track**      | **Parallel**                                                                                               |
| **License**            | [MIT](./LICENSE) (root `LICENSE` — visible in GitHub About)                                                |


> **For judges (60 seconds):** open the [live app](https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/) → sign in → upload a short screenplay (or use sample text from `[tests/scripts/](./tests/scripts/)`) → watch specialists research via Parallel → review findings → attempt export (gatekeeper holds until high-risk items are decided). Then skim [Partner + Google proof](#partner--google-cloud--imported-and-called-in-code) below.

---



## The problem

Before a film can be insured and released, a **clearance house** must flag every name, business, brand, song, address, and quote that could trigger an E&O claim. That work is slow, expensive, and mostly manual search — while production calendars keep shrinking.

**ScriptClear AI** is a multi-agent system that performs the first pass the way a clearance researcher would: extract entities from the script, ground them in the text, research the real world with cited sources, score risk with explainable rules, and force a **human legal decision** before any report can leave the system.

It does **not** auto-approve legal risk. A gatekeeper blocks export until outstanding high-risk items are resolved.

---



## What’s in the box


| Area                     | Implementation                                                                                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Agent crew**           | Dedicated ADK agents for extraction, six research specialties, risk scoring, and summary — orchestrated end-to-end in `[orchestrator.py](./orchestrator.py)` |
| **Parallel research**    | Search MCP via ADK `McpToolset`; every research specialist calls it for cited, real-world findings                                                           |
| **Google Cloud**         | Cloud Run (live), Firestore run store + vector RAG, GCS for scripts/reports, Firebase Auth, Secret Manager                                                   |
| **Clearance safeguards** | Deterministic grounding, explainable risk rubrics, per-entity legal review, export gatekeeper                                                                |
| **Reproducibility**      | Public demo, sample screenplays under `[tests/scripts/](./tests/scripts/)`, pytest suite                                                                     |
| **Product surface**      | React workflow: upload → streamed progress → findings → human review → PDF report                                                                            |


---



## How it works

```
Upload screenplay (PDF / TXT)
        │
        ▼
  Extraction agent (Gemini / ADK)
        │
        ▼
  Deterministic grounding check
        │
        ▼
  ┌─────┴──────────────────────────────────────┐
  │  Specialist agents (concurrent)            │
  │  business · character · music · trademark  │
  │  address · literary                        │
  │       │                                    │
  │       ▼                                    │
  │  Parallel Search MCP  (cited web research) │
  │  + exact cache + Firestore vector RAG      │
  └─────┬──────────────────────────────────────┘
        ▼
  Risk scoring → executive summary
        ▼
  Human legal review (per entity)
        ▼
  Gatekeeper → clearance PDF (only if cleared)
```

---



## Partner + Google Cloud — imported and called in code

Judges: these are the files that prove runtime use (not documentation theater).

### Parallel (partner track)


| What                                                                            | Where                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MCP client (`McpToolset`, `https://search.parallel.ai/mcp`, `PARALLEL_API_KEY`) | `[gatekeeper/parallel_mcp.py](./gatekeeper/parallel_mcp.py)`                                                                                                                                                                                                                                                                                                                                                              |
| Specialists that call Parallel                                                  | `[agents/business_specialist.py](./agents/business_specialist.py)`, `[character_name_specialist.py](./agents/character_name_specialist.py)`, `[music_specialist.py](./agents/music_specialist.py)`, `[trademark_brand_specialist.py](./agents/trademark_brand_specialist.py)`, `[address_specialist.py](./agents/address_specialist.py)`, `[literary_reference_specialist.py](./agents/literary_reference_specialist.py)` |
| Live MCP smoke test                                                             | `[tests/verify_parallel_mcp.py](./tests/verify_parallel_mcp.py)`                                                                                                                                                                                                                                                                                                                                                          |
| Docs                                                                            | [Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp) · [ADK MCP tools](https://google.github.io/adk-docs/tools-custom/mcp-tools/)                                                                                                                                                                                                                                                                  |




### Google ADK + Gemini + Cloud


| What                                      | Where                                                                                                              |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Pipeline orchestration (`Runner`, agents) | `[orchestrator.py](./orchestrator.py)`                                                                             |
| Extraction / risk / summary agents        | `[agents/](./agents/)`                                                                                             |
| Firestore run persistence                 | `[storage/firestore_run_store.py](./storage/firestore_run_store.py)`                                               |
| Firestore vector RAG                      | `[research/vector_store.py](./research/vector_store.py)`, `[research/embeddings.py](./research/embeddings.py)`     |
| Cloud Storage uploads                     | `[storage/file_store.py](./storage/file_store.py)`, `[gatekeeper/cloud_storage.py](./gatekeeper/cloud_storage.py)` |
| Firebase Auth                             | `[gatekeeper/firebase_auth.py](./gatekeeper/firebase_auth.py)`, `[frontend/src/auth/](./frontend/src/auth/)`       |
| Cloud Run deploy                          | `[cloudbuild.yaml](./cloudbuild.yaml)`, `[scripts/deploy.ps1](./scripts/deploy.ps1)`                               |
| HTTP API                                  | `[api/main.py](./api/main.py)`                                                                                     |


---



## Demo walkthrough (for the 3-minute video + judges)

Suggested script — show the **working product**, not a trailer:

1. **Problem (15s)** — E&O clearance is manual; one missed brand/song can sink insurance
2. **Upload (20s)** — PDF/TXT into the live app
3. **Agents at work (60s)** — streaming progress; call out Parallel-backed specialists by name
4. **Findings (45s)** — open an entity: script location, cited research, risk rule that fired
5. **Human + gatekeeper (40s)** — decide a high-risk item; show export blocked until resolved; export PDF
6. **Stack close (20s)** — Google ADK + Gemini + Parallel MCP + Firestore/GCS/Cloud Run

---



## Tech stack


| Layer            | Choice                                                           |
| ---------------- | ---------------------------------------------------------------- |
| Agent framework  | **Google ADK** (`LlmAgent`, `LoopAgent`, `Runner`, `McpToolset`) |
| Models           | **Gemini** (`gemini-3.6-flash`; embeddings via `google-genai`)   |
| Partner research | **Parallel Search MCP**                                          |
| API              | FastAPI + Uvicorn                                                |
| Frontend         | React 19 · Vite 8 · React Router · GSAP · Lenis                  |
| Auth             | Firebase Authentication                                          |
| Data             | Cloud Firestore (runs + vector RAG) · Cloud Storage              |
| Deploy           | Cloud Run · Cloud Build · Artifact Registry · Secret Manager     |


---



## Repository layout

```
agents/          ADK extraction, specialists, risk, summary
api/             FastAPI surface (clearance + streaming)
gatekeeper/      Parallel MCP, Firebase auth, GCS, export gate
research/        Exact cache + Firestore vector RAG
schemas/         Shared Pydantic models
storage/         Firestore runs + GCS files
frontend/        Product UI + marketing landing
tests/           Unit/integration + sample screenplays
orchestrator.py  End-to-end clearance pipeline
cloudbuild.yaml  Production deploy to Cloud Run
LICENSE          MIT
```

---



## Quick start (local)



### Prerequisites

- Python 3.11+ · Node.js 20+  
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`  
- `PARALLEL_API_KEY`  
- Firebase web config + (recommended) GCP Firestore/GCS + ADC: `gcloud auth application-default login`



### 1. Configure

```bash
git clone https://github.com/AntonyJomy/agentic-cinema.git
cd agentic-cinema
cp .env.example .env   # fill keys — see table below
```

Copy all `VITE_FIREBASE_*` values into `frontend/.env` as well.

### 2. API

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000
```



### 3. UI

```bash
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) (Vite proxies `/clearance`, `/extract-script`, `/health` → `:8000`).

### 4. CLI only

```bash
python orchestrator.py tests/scripts/test_screenplay.txt
```



### Key environment variables


| Variable                                   | Required          | Purpose                         |
| ------------------------------------------ | ----------------- | ------------------------------- |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY`        | Yes               | Gemini / ADK                    |
| `PARALLEL_API_KEY`                         | Yes               | Parallel Search MCP             |
| `GEMINI_MODEL`                             | No                | Default `gemini-3.6-flash`      |
| `PIPELINE_CONCURRENCY`                     | No                | Concurrent specialist runs      |
| `GCS_BUCKET_NAME`                          | Persistence       | Script / report storage         |
| `FIRESTORE_PROJECT` / `FIRESTORE_DATABASE` | Persistence / RAG | Runs + vectors                  |
| `FIREBASE_PROJECT_ID` + `VITE_FIREBASE_*`  | Auth / UI         | Firebase                        |
| `AUTH_MODE`                                | No                | `firebase`                      |
| `CLEARANCE_STORE`                          | No                | `auto` / `firestore` / `memory` |


Full template: `[.env.example](./.env.example)`. Cloud secrets live in Secret Manager via `[scripts/setup-gcp.ps1](./scripts/setup-gcp.ps1)`.

---



## Deploy to Google Cloud

This project is hosted on **Google Cloud Run** in our hackathon GCP project. Cloud Build builds two images (API + web), pushes them to Artifact Registry, and deploys both services. Secrets stay in Secret Manager — never in the repo.

### Our deployment targets


| Resource               | Value                                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| **GCP project**        | `script-clearance-hackathon`                                                                               |
| **Region**             | `australia-southeast1`                                                                                     |
| **Artifact Registry**  | `agentic-cinema`                                                                                           |
| **API service**        | `agentic-cinema-api`                                                                                       |
| **Web service**        | `agentic-cinema-web`                                                                                       |
| **Firestore database** | `script-clearance-db`                                                                                      |
| **GCS bucket**         | `script-clearance-scripts` (set as `GCS_BUCKET_NAME` in `.env`)                                            |
| **Live frontend**      | [https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/](https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/) |


Pipeline config: `[cloudbuild.yaml](./cloudbuild.yaml)` · one-time setup: `[scripts/setup-gcp.ps1](./scripts/setup-gcp.ps1)` · deploy: `[scripts/deploy.ps1](./scripts/deploy.ps1)`.

### Prerequisites

1. [Google Cloud SDK](https://cloud.google.com/sdk) (`gcloud`) installed
2. Access to project `script-clearance-hackathon` (Owner/Editor)
3. Root `.env` filled from `[.env.example](./.env.example)`, including at least:

```env
GEMINI_API_KEY=...
PARALLEL_API_KEY=...
GCS_BUCKET_NAME=script-clearance-scripts
FIRESTORE_PROJECT=script-clearance-hackathon
FIRESTORE_DATABASE=script-clearance-db
FIREBASE_PROJECT_ID=script-clearance-hackathon
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=script-clearance-hackathon.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=script-clearance-hackathon
VITE_FIREBASE_APP_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
```



### Step 1 — Authenticate and select the project

```bash
gcloud auth login
gcloud config set project script-clearance-hackathon
gcloud auth application-default login
```



### Step 2 — Create data resources (first time only)

If the bucket / Firestore DB do not exist yet:

```bash
# Cloud Storage (screenplays + PDF reports)
gcloud storage buckets create gs://script-clearance-scripts \
  --project=script-clearance-hackathon \
  --location=australia-southeast1

# Firestore (Native mode) — create database script-clearance-db in Console
# or via gcloud if your org allows:
# gcloud firestore databases create --database=script-clearance-db \
#   --location=australia-southeast1 --type=firestore-native
```

Firebase Authentication: enable your sign-in providers in the [Firebase Console](https://console.firebase.google.com/) for project `script-clearance-hackathon`.

### Step 3 — One-time GCP pipeline setup

Enables Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Firestore, Storage, and IAM; creates the `agentic-cinema` Artifact Registry repo; seeds `GEMINI_API_KEY`, `PARALLEL_API_KEY`, and `FIREBASE_WEB_API_KEY` from `.env`; grants Cloud Build / Cloud Run service accounts the roles they need.

```powershell
.\scripts\setup-gcp.ps1
# Equivalent explicit form:
# .\scripts\setup-gcp.ps1 -ProjectId script-clearance-hackathon -Region australia-southeast1
```



### Step 4 — Deploy API + frontend

Reads project + Firebase config from `.env`, submits `[cloudbuild.yaml](./cloudbuild.yaml)`, builds/pushes images, deploys both Cloud Run services, then wires CORS to the frontend origin.

```powershell
.\scripts\deploy.ps1
# Optional: .\scripts\deploy.ps1 -ProjectId script-clearance-hackathon -Region australia-southeast1
```

What Cloud Build does:

1. Build & push **API** image → deploy `agentic-cinema-api` (2 GiB / 2 CPU, 3600s timeout; secrets for Gemini + Parallel)
2. Build & push **web** image (Vite baked with live API URL + Firebase config) → deploy `agentic-cinema-web`
3. Update API `CORS_ORIGINS` to the Cloud Run frontend URL



### Step 5 — Confirm URLs and authorize Firebase

```bash
gcloud run services describe agentic-cinema-web \
  --project script-clearance-hackathon \
  --region australia-southeast1 \
  --format='value(status.url)'

gcloud run services describe agentic-cinema-api \
  --project script-clearance-hackathon \
  --region australia-southeast1 \
  --format='value(status.url)'
```

Current live app: [https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/](https://agentic-cinema-web-qtltf5pl4q-ts.a.run.app/)

After the **first** deploy (or any new hostname), add the frontend host to:

**Firebase Console → Authentication → Settings → Authorized domains**  
e.g. `agentic-cinema-web-qtltf5pl4q-ts.a.run.app`

### Step 6 — Firestore vector index (RAG)

Research cache / semantic RAG needs the composite vector index on `entity_research_vectors`:

```bash
gcloud firestore indexes composite create \
  --project=script-clearance-hackathon \
  --database=script-clearance-db \
  --field-config-from-file=firestore.indexes.json
```

Or: `firebase deploy --only firestore:indexes`

Index: `entity_type` (ASC) + `embedding` (vector, 1536 dims). Helpers: `scripts/create_vector_index.py`, `scripts/backfill_rag.py`. See also `MIGRATION_GUIDE.md`.

### Redeploy after code changes

```powershell
.\scripts\deploy.ps1
```

No need to re-run `setup-gcp.ps1` unless you rotate secrets or recreate IAM/Artifact Registry.

---



## Tests

```bash
source .venv/bin/activate
pytest tests/ -q
python tests/verify_parallel_mcp.py   # needs PARALLEL_API_KEY
```

Sample screenplays: `[tests/scripts/](./tests/scripts/)`.

---



## API (summary)


| Method | Path                           | Description      |
| ------ | ------------------------------ | ---------------- |
| `GET`  | `/health`                      | Liveness         |
| `POST` | `/extract-script`              | PDF / TXT → text |
| `POST` | `/clearance`                   | Full pipeline    |
| `POST` | `/clearance/stream`            | NDJSON progress  |
| `GET`  | `/clearance/{run_id}`          | Load run         |
| `POST` | `.../entities/{id}/decision`   | Legal decision   |
| `POST` | `/clearance/{run_id}/decision` | Overall decision |


Bearer Firebase ID token required when `AUTH_MODE=firebase`.

---

## License

MIT © 2026 Antony Jomy Kolanchery — see [LICENSE](./LICENSE).

## Acknowledgments

[Google ADK](https://google.github.io/adk-docs/) · [Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp) · [Gemini](https://ai.google.dev/) · [Firebase](https://firebase.google.com/) · [Cloud Run](https://cloud.google.com/run)