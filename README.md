# Atlas

Atlas is an AI chatbot for research, diagrams, workspace tools, and integrations. It pairs a FastAPI backend with a React frontend and stores data in SQLite by default. Automated tests are not included in this published tree.

## Stack

- **Backend:** FastAPI, Python (`uv` for deps and runs)
- **Frontend:** React + Vite
- **Database:** SQLite (default); pluggable storage for other backends

## Features

- Chat with streaming replies
- Research and web lookup
- Diagram generation (Mermaid)
- Slash commands
- Conversation memory
- Integrations and MCP tools
- Freelance helpers (proposals, jobs, related workflows)
- Workspace for projects, proposals, and jobs
- Auth and admin (first registered user is admin)
- Pluggable storage backends

## Prerequisites

- [Node.js](https://nodejs.org/) (npm)
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Git

## Setup

1. **Clone the repo**

   ```bash
   git clone https://github.com/meet-hirpara/atlas
   cd atlas
   ```

2. **Backend**

   ```bash
   cd backend
   copy .env.example .env   # Windows; use cp on macOS/Linux
   ```

   Edit `backend/.env` and fill in required keys (see [Environment](#environment)). Then install and run:

   ```bash
   uv sync
   ```

   Start with `start-backend.bat` from the repo root, or:

   ```bash
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. **Frontend**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Or use `start-frontend.bat` from the repo root.

4. **Optional — both at once**

   From the repo root, run `start-atlas.bat` to launch backend and frontend together.

## Environment

Copy `backend/.env.example` → `backend/.env` and set at least:

| Variable | Purpose |
|---|---|
| `MISTRAL_API_KEY` | LLM API key (required) |
| `ATLAS_SECRET_KEY` | Encrypts stored integration/MCP credentials |
| `ATLAS_JWT_SECRET` | Signs login session JWTs |

Optional keys (Tavily, YouTube, etc.) are documented in `.env.example`.

**Never commit `.env` or other secrets.** Only `.env.example` belongs in the repo.

## Scripts

| Script / command | Description |
|---|---|
| `start-atlas.bat` | Start backend and frontend together |
| `start-backend.bat` | Sync deps and run API on port 8000 |
| `start-frontend.bat` | Run Vite dev server |
| `cd frontend && npm run build` | Production frontend build |

## Auth

Register from the UI. The **first registered user becomes admin**; later accounts are regular users.

## License

Private project — no public license file is included.
