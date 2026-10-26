# TraceGuard AI — Incident Investigation Workspace

TraceGuard AI is an evidence-linked incident investigation workspace designed for Site Reliability Engineers (SREs), DevOps engineers, and on-call responders. It deterministically parses multi-format application logs (JSON, plaintext stack traces, Nginx/Apache access logs), detects critical anomaly patterns (such as retry storms and error spikes), constructs causal hypothesis chains, preserves original source line numbers, and provides multi-tenant workspaces backed by PostgreSQL, Argon2id password hashing, and JWT session authentication.

---

## Architecture & Technology Stack

- **Backend**: FastAPI 0.111+ (Python 3.10+) running on `http://127.0.0.1:8010`
- **Frontend**: React 19, TypeScript, Vite running on `http://localhost:5173`
- **Database**: PostgreSQL 16 (Docker Compose) with native `psycopg` driver running on host port `5434` (internal container port `5432`)
- **ORM & Migrations**: SQLAlchemy 2.0 (Declarative Mapped), Alembic 1.13+ (Strict transactional DDL)
- **Security**: Argon2id password hashing, PyJWT authentication, HttpOnly cookies, Two-tier brute-force rate limiter, Multi-tenant Organization RBAC (anti-IDOR)
- **Deployment**:
  - **Docker Compose**: Dedicated local development (`compose.yaml`) & multi-container production (`compose.prod.yaml`)
  - **Render**: Blueprint-as-Code (`render.yaml`) for managed FastAPI backend & PostgreSQL
  - **Vercel**: SPA deployment (`frontend/vercel.json`) with client-side routing rewrites
  - **Kubernetes**: Declarative manifests (`k8s/`) for scalable container orchestration

```
┌────────────────────────────────────────────────────────┐
│                   React 19 + Vite UI                   │
│      Dark-mode SRE UI | Visual Timeline | Evidence     │
└───────────────────────────┬────────────────────────────┘
                            │ (JSON / REST API)
┌───────────────────────────▼────────────────────────────┐
│                  FastAPI Backend (8010)                │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Ingestion & Redaction (5 MB cap, regex sanitizers)  │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ Deterministic Engine (Timestamp norm, anomaly det) │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ Security & Auth (Argon2id, JWT, 2-tier Rate Limit) │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ Tenancy Guard (SQLAlchemy 2.0, Anti-IDOR filters)  │ │
│ └────────────────────────────────────────────────────┘ │
└───────────────────────────┬────────────────────────────┘
                            │ (psycopg driver)
┌───────────────────────────▼────────────────────────────┐
│               PostgreSQL 16 Database (5434)            │
│          traceguard_postgres_data (Persistent)         │
└────────────────────────────────────────────────────────┘
```

---

## 1. Prerequisites

- **Python**: 3.10+ (tested with Python 3.11 and 3.14)
- **Node.js**: 18+ and npm
- **Docker & Docker Compose**: Docker Desktop (Windows/macOS) or Docker Engine (Linux)

---

## 2. Environment Configuration

Copy the template configuration file:

```powershell
cp .env.example .env
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+psycopg://...` | Full database connection string using the psycopg3 driver |
| `POSTGRES_USER` | Yes | `traceguard_user` | Database user for Docker Compose and backend |
| `POSTGRES_PASSWORD` | Yes | — | Database user password (specify your own secure secret) |
| `POSTGRES_DB` | Yes | `traceguard_db` | PostgreSQL database name |
| `SECRET_KEY` | Yes | — | Cryptographic signing key for JWT tokens (32+ chars in prod) |
| `ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `1440` | Session lifetime in minutes (24 hours) |
| `ENVIRONMENT` | No | `development` | Environment mode (`development` or `production`) |
| `COOKIE_SECURE` | No | `false` | Enable `Secure` cookie flag over HTTPS in production |
| `CORS_ORIGINS` | No | `""` | Comma-separated list of additional allowed origins |
| `TRUSTED_PROXIES` | No | `""` | Comma-separated trusted reverse proxy CIDRs/IPs |
| `HOST` | No | `127.0.0.1` | Local backend bind address |
| `PORT` | No | `8010` | Backend API port (TraceGuard reserves port 8010) |
| `VITE_API_URL` | No | `http://127.0.0.1:8010` | Backend API URL for the frontend |

---

## 3. Database Startup & Migrations

TraceGuard AI includes a dedicated development compose definition (`compose.yaml`) bound to host port `5434` with a persistent named volume `traceguard_postgres_data`. This avoids port collisions with default local PostgreSQL instances on port 5432.

### Start PostgreSQL
```powershell
docker compose up -d
```

### Verify Container Health
```powershell
docker compose ps
```

### Apply Database Migrations
```powershell
cd backend
python -m alembic upgrade head
```

---

## 4. Starting the Application

Always run the backend on port **8010** and the frontend on port **5173**.

### Terminal 1 — Backend API
```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

### Terminal 2 — Frontend UI
```powershell
cd frontend
npm install
npm run dev
```

Open your browser to: **`http://localhost:5173`**

---

## 5. User Workflow & Features

1. **Authentication & Multi-Tenancy**:
   - Navigate to `http://localhost:5173`.
   - Click **Sign In / Register** to create a user account and organization.
   - User credentials are encrypted with Argon2id and authenticated via signed JWT HttpOnly cookies.
2. **Log Ingestion & Automated Redaction**:
   - Upload a log file (up to 5 MB) or click **Load Sample Incident**.
   - Accepts JSON lines, plaintext stack traces, and Nginx/Apache logs.
   - Automated sanitization masks API keys, bearer tokens, database passwords, and AWS credentials prior to analysis and storage.
3. **Deterministic Anomaly & Hypothesis Engine**:
   - Detects retry storms (repeated rapid retries), error spikes, and cascading failures across services.
   - Classifies findings into **Observed Facts**, **Detected Patterns**, and **Unconfirmed Hypotheses**.
4. **Evidence-Linked Timeline**:
   - Inspect the interactive chronological timeline with component badges and exact original source line numbers (`L#`).
   - Unrecognized lines are preserved and surfaced with `UNINTERPRETED` badges rather than silently dropped.
5. **Incident Workspace Management**:
   - Click **Save to Workspace** to persist investigations to PostgreSQL.
   - Use **Saved Incidents** to browse, search, update severity/summaries, or delete past incident records with strict anti-IDOR tenant isolation.

---

## 6. API Documentation

Interactive OpenAPI documentation is available when the backend is running:
- **Swagger UI**: `http://127.0.0.1:8010/docs`
- **ReDoc**: `http://127.0.0.1:8010/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8010/openapi.json`

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service liveness healthcheck |
| `GET` | `/api/health/db` | Database connectivity diagnostic (credentials masked) |
| `POST` | `/api/auth/signup` | Register a new user and tenant organization |
| `POST` | `/api/auth/login` | Authenticate and obtain JWT session cookie |
| `GET` | `/api/auth/me` | Fetch active user profile and organization role |
| `POST` | `/api/auth/logout` | Terminate session cookie |
| `POST` | `/api/analyze` | Parse logs and generate evidence-linked investigation |
| `GET` | `/api/incidents` | List incidents scoped to user's organization |
| `POST` | `/api/incidents` | Save new incident investigation |
| `GET` | `/api/incidents/{id}` | Retrieve incident details (tenant-isolated) |
| `PATCH` | `/api/incidents/{id}` | Update incident title, severity, or summary |
| `DELETE` | `/api/incidents/{id}` | Delete incident (creator or owner role required) |

---

## 7. Automated Testing & Verification

TraceGuard AI includes a 100% automated test suite:

### Backend Pytest Suite
```powershell
cd backend
python -m pytest tests/ -v
```
- **171 tests across 10 test modules** covering deterministic parsing, anomaly detection rules, regression, Argon2id security, JWT verification, multi-tenant anti-IDOR isolation, and incident workflows.

### Frontend Typecheck, Lint, and Build
```powershell
cd frontend
npm run lint       # oxlint check (0 errors, 0 warnings)
npm run build      # tsc -b && vite build (production bundle)
```

### Docker Compose Validation
```powershell
docker compose config --quiet
docker compose -f compose.prod.yaml config --quiet
```

---

## 8. Deployment Guides

### A. Deploy to Render (Backend + Managed PostgreSQL)

The repository includes a ready-to-use Render Blueprint (`render.yaml`):

1. Connect your GitHub repository to [Render](https://render.com/).
2. Select **New** → **Blueprint**.
3. Point Render to your repository. Render automatically reads `render.yaml` and provisions:
   - A managed PostgreSQL 16 database (`traceguard-db`).
   - A Python web service (`traceguard-backend`) running `uvicorn app.main:app` on port `$PORT`.
4. Configure environment variables in the Render dashboard:
   - Set `CORS_ORIGINS` to your frontend Vercel domain (e.g. `https://traceguard.vercel.app`).
   - `SECRET_KEY` is automatically generated by Render.
   - `DATABASE_URL` is automatically linked from the managed database.

### B. Deploy to Vercel (Frontend SPA)

The frontend is configured with `frontend/vercel.json` for seamless client-side SPA routing:

1. Import your repository into [Vercel](https://vercel.com/).
2. Set the **Root Directory** to `frontend`.
3. In **Environment Variables**, configure:
   - `VITE_API_URL`: Your Render backend URL (e.g., `https://traceguard-backend.onrender.com`).
4. Click **Deploy**. Vercel will run `npm run build` and serve the production distribution.

### C. Full-Stack Docker Compose (Production)

For single-server deployment (VPS, AWS EC2, DigitalOcean):

```powershell
# Set production environment variables in .env (ensure COOKIE_SECURE=true if using TLS)
docker compose -f compose.prod.yaml up -d --build
```
This launches:
- `db`: PostgreSQL 16 Alpine with SCRAM-SHA-256 authentication and resource limits.
- `backend`: Multi-stage Python 3.11 container running as non-root `appuser`.
- `frontend`: Multi-stage Node 20 build served by an unprivileged Alpine Nginx reverse proxy on port 8080.

### D. Kubernetes (k8s/)

Declarative Kubernetes manifests are located in `k8s/`:
- `namespace.yaml`, `configmap.yaml`, `secret-template.yaml`
- `backend-deployment.yaml`, `backend-service.yaml`
- `frontend-deployment.yaml`, `frontend-service.yaml`
- `ingress.yaml`

To deploy:
```bash
kubectl apply -f k8s/namespace.yaml
# Copy k8s/secret-template.yaml to secrets.yaml, populate real secrets, and apply:
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret-template.yaml
kubectl apply -f k8s/backend-deployment.yaml -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml -f k8s/frontend-service.yaml
kubectl apply -f k8s/ingress.yaml
```

---

## 9. Security & Governance

- **Argon2id Hashing**: Passwords are saved using Argon2id parameters (time cost: 3, memory cost: 64 MiB, parallelism: 4). Plaintext credentials are never stored or logged.
- **JWT & Session Protection**: Tokens are delivered via HttpOnly, SameSite=Lax cookies with configurable `Secure` flags to prevent XSS exfiltration.
- **Two-Tier Brute-Force Rate Limiting**: In-memory sliding-window limiter throttles failed login attempts per client IP (30/min) and per IP+email pair (5/min), preventing credential stuffing.
- **Anti-IDOR Multi-Tenant Authorization**: All incident endpoints enforce organization membership checks at the database query level. Requests targeting resources outside the caller's organization return HTTP 404 to prevent resource discovery.
- **Credential Redaction**: Raw logs undergo regex-based sanitization before AI dispatch or persistent storage.
- **Adversarial Prompt Defense**: Untrusted log payloads are isolated from system prompts, and prompt injection signatures trigger safe fallback modes.

---

## 10. Repository Maintenance & Hackathon Deliverables

- **Root `README.md`**: Authoritative system architecture, setup, testing, and deployment guide.
- **`DEMO_SCRIPT.md`**: Step-by-step 2–3 minute video presentation walkthrough for hackathon submission.
- **`SUBMISSION_DRAFT.md`**: Complete Devpost submission draft (elevator pitch, architecture diagram, challenges, and roadmap).
- **`devpost/`**: Hackathon planning artifacts (`scope.md`, `prd.md`, `spec.md`, `checklist.md`).
- **`.agents/`**: Authoritative Antigravity IDE workspace skill definitions.
