# AURA local development

The root `README.md` is the supplied product specification, preserved verbatim. It includes the original proposed roadmap, not a claim that every milestone is complete. Current implementation and verification status is summarized in `IMPLEMENTATION_STATUS.md`.

## Run the application

Prerequisites: Docker Compose. Optional: install Ollama locally and pull a chat model (`qwen2.5:7b`) and embedding model (`nomic-embed-text`) for local model-backed answers and embeddings.

```sh
docker compose up --build
```

Open `http://localhost:3000`; the API is at `http://localhost:8000` and interactive API docs are at `/docs`. Compose binds ports to loopback. PostgreSQL uses a local-only trust-auth development configuration; do not reuse it outside a machine you control. User documents are stored in the Compose `aura-uploads` volume and records/vectors in `aura-postgres`.

Without Ollama, AURA uses a local deterministic hashed-token vector and an extractive evidence response. This fallback does not require network access or cloud credentials, but is less semantically capable than a configured local Ollama model. Ollama requests are restricted to loopback HTTP URLs or Docker Desktop's explicit `host.docker.internal` host bridge.

## Run backend checks without Docker

Requires Python 3.11+ and a reachable PostgreSQL with pgvector for normal operation. SQLite is used only by the automated tests.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e "backend[dev]"
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```sh
cd backend
pytest -q
```

Set `DATABASE_URL`, `UPLOAD_DIR`, and optionally `OLLAMA_BASE_URL` in the environment. If `JWT_SECRET_KEY` is unset, the API generates a random process-local signing key: tokens expire on restart. Set an independently generated secret for persistent local sessions. Never publish `.env` files.

## Run the frontend without Docker

```sh
npm --prefix services/web install
npm --prefix services/web run dev
```

The UI reads `NEXT_PUBLIC_API_URL` at build time (default `http://localhost:8000/api/v1`).

## Data and privacy

Uploads and extracted chunks remain in the local API/database by default. No cloud services or hosted AI API are configured. Back up or delete the local volumes as appropriate; no cloud deletion/retention guarantees apply.
