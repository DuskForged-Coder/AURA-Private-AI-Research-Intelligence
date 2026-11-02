# Implementation status

**MVP implementation:** implemented; backend tests, frontend production build, and a browser-driven registration-to-cited-answer smoke test pass. PostgreSQL/pgvector and Compose runtime validation remain unverified because Docker is not installed in the current environment.

## Implemented scope

- FastAPI auth with Argon2 password hashes, bearer access tokens, account ownership filtering, and protected document/conversation operations.
- Local PDF, DOCX, TXT, and Markdown extraction; page references for PDFs; size/format validation; chunking; local file storage.
- PostgreSQL/pgvector schema and Alembic migration; local hashed-token embedding fallback and optional loopback-only Ollama embedding/generation.
- Scoped passage search, citation payloads, extractive fallback answers, and abstention when matching evidence is insufficient.
- Next.js workspace for sign-in/registration, upload/list/delete, search, questions, and citation inspection.
- Docker Compose local development stack. OCR, hosted/cloud inference, org administration, worker scaling, evaluation dashboards, and production deployment are not implemented.

## Verification

- Backend: `PYTHONPATH=backend python3 -m pytest -q backend/tests` — 6 passed. Tests use SQLite for auth, ownership, ingestion, retrieval/citations, abstention, malformed-file rejection, and supported-format extraction.
- Python syntax: `python3 -m compileall -q backend/app backend/migrations backend/tests` — passed.
- Migration metadata: `PYTHONPATH=backend python3 -m alembic -c backend/alembic.ini heads` — `0001_initial (head)`.
- Frontend: `npm --prefix services/web run build` — passed with Next.js 16.4.3.
- Browser smoke test: registered an account, uploaded a text file, searched its passage, and received a cited answer against the local API.
- Dependency audit: `npm --prefix services/web audit --audit-level=high` — 0 vulnerabilities.
- README: retains the supplied specification and now reflects the implemented MVP, current setup commands, API routes, and verified roadmap status.
- Not verified here: PostgreSQL/pgvector migration and live database behavior, Docker Compose startup, or full browser E2E against PostgreSQL. Docker is unavailable in this environment.
