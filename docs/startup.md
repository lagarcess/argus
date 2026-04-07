# 🚀 Argus – Local Development Setup & Launch Guide

This guide walks you through setting up the Argus project locally with all dependencies properly configured.

---

## 📋 Prerequisites

Before starting, ensure you have:

- **Bun** (JavaScript/TypeScript runtime & package manager)
  - Install: https://bun.sh
  - Windows: Use Bun native or WSL2
- **Python 3.10+**
  - Download: https://www.python.org/downloads/
- **Poetry** (Python dependency manager)
  - Install: https://python-poetry.org/docs/#installation

Verify installations:

```bash
bun --version      # Should be ≥1.0.0
python --version   # Should be ≥3.10.0
poetry --version   # Should be ≥1.7.0
```

---

## 🔧 Step 1: Install Dependencies

### Backend (Python)

```bash
# Navigate to project root
cd d:\Users\garce\git-repos\argus

# Install Python dependencies via Poetry
poetry install

# This installs:
# - Production deps: FastAPI, Numba, VectorBT, pandas-ta-classic, Supabase, etc.
#   - faker (for generating test data)
#   - pytest, pytest-asyncio, httpx (for testing APIs)
```

### Frontend (JavaScript/TypeScript)

```bash
# Navigate to frontend directory
cd web

# Install dependencies via Bun
bun install

# This installs:
# - Production: Next.js, React, Supabase, shadcn/ui, Recharts, etc.
# - Dev: TypeScript, Tailwind, testing libraries, Prettier, etc.
# - Mock data generator: @faker-js/faker (for development before backend ready)
```

---

## 📁 Step 2: Configure Environment Variables

### Backend Configuration

```bash
# Root directory: .env

# Already provided with placeholder/example values
# Key variables:
# - ALPACA_API_KEY / ALPACA_SECRET_KEY (market data)
# - SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY (auth & DB)
# - SUPABASE_JWT_SECRET (token verification)

# Copy example if needed:
# cp .env.example .env
```

### Frontend Configuration

```bash
# Frontend directory: web/.env.local

# Create from example:
cp web/.env.example web/.env.local

# Edit with your values (key variables):
# NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1  (backend endpoint)
# NEXT_PUBLIC_MOCK_API=false                         (toggle mock data)
# NEXT_PUBLIC_SUPABASE_URL=https://...              (Supabase project)
# NEXT_PUBLIC_SUPABASE_ANON_KEY=...                 (Supabase public key)
```

**For Frontend Development Before Backend is Ready:**

```bash
# Set NEXT_PUBLIC_MOCK_API=true in web/.env.local
# Frontend will generate realistic fake data using @faker-js/faker
# No backend required; perfect for parallel development
```

---

## 🗄️ Step 3: Prepare Database (if needed)

If using Supabase, run migrations:

```bash
# Option 1: Supabase CLI (if installed)
supabase db push

# Option 2: Manual SQL
# Visit Supabase Dashboard > SQL Editor
# Run migrations from: supabase/migrations/
```

---

## ▶️ Step 4: Launch the Application

### Option A: Development Mode (Parallel Terminals)

**Terminal 1 – Backend (FastAPI)**

```bash
# Root directory
cd d:\Users\garce\git-repos\argus

# Activate Poetry environment
poetry shell

# Run FastAPI server (auto-reload on file changes)
fastapi dev src/argus/api/main.py

# Server runs at: http://localhost:8000
# API docs: http://localhost:8000/docs
```

**Terminal 2 – Frontend (Next.js with Bun)**

```bash
# Frontend directory
cd web

# Run Next.js dev server with Bun
bun run dev

# App runs at: http://localhost:3000
# Auto-reloads on file changes
```

### Option B: Backend Only (API Testing)

```bash
cd d:\Users\garce\git-repos\argus
poetry shell
fastapi dev src/argus/api/main.py

# Test endpoints:
# - GET  http://localhost:8000/health               (health check)
# - POST http://localhost:8000/api/v1/backtests    (run backtest)
# - etc.

# Full API docs at: http://localhost:8000/docs
```

### Option C: Frontend Only with Mock Data (No Backend Needed)

```bash
cd web

# Edit .env.local:
# NEXT_PUBLIC_MOCK_API=true

# Run with Bun
bun run dev

# Visits to http://localhost:3000 will show fake data
# Useful for UI development while backend builds
```

---

## 🧪 Step 5: Run Tests

### Backend Unit Tests

```bash
cd d:\Users\garce\git-repos\argus

# Run all tests with coverage report
poetry shell
pytest

# Run specific test file
pytest tests/test_engine.py

# Run with verbose output
pytest -v

# Run only marked tests
pytest -m slow  # Only slow performance tests
```

### Frontend Tests

```bash
cd web

# Run all frontend tests (Vitest-compatible)
bun test

# Run in watch mode (re-run on file changes)
bun test:watch
```

---

## 🎨 Code Formatting & Linting

### Format Code

```bash
# Frontend (Prettier)
cd web
bun run format

# Backend (Ruff)
cd ..
poetry shell
ruff format src/ tests/
```

### Lint Code

```bash
# Frontend (ESLint)
cd web
bun run lint

# Backend (Ruff)
cd ..
poetry shell
ruff check src/ tests/
```

---

## 🔍 Workflow: API-First Development

### When Backend & Frontend Teams Work in Parallel:

**Backend Developer:**

1. Define API contract (endpoints, schemas, error codes)
2. Run `fastapi dev src/argus/api/main.py`
3. Document at `http://localhost:8000/docs`
4. Build endpoints one by one

**Frontend Developer:**

1. Set `NEXT_PUBLIC_MOCK_API=true` in `.env.local`
2. Run `bun run dev`
3. Use mock data from `@faker-js/faker`
4. Build UI pages independently
5. Mock responses in `web/lib/mockApi.ts`
6. When backend is ready, flip `NEXT_PUBLIC_MOCK_API=false` and test integration

---

## 📊 Project Structure

```
argus/
├── src/
│   └── argus/
│       ├── api/              # FastAPI endpoints
│       ├── engine.py         # Core backtest engine
│       ├── config.py         # Configuration
│       └── analysis/         # Indicators, patterns, harmonics (Numba JIT)
├── web/
│   ├── app/                  # Next.js pages (Landing, Builder, Results, etc.)
│   ├── components/           # React components (Auth, Sidebar, etc.)
│   ├── lib/
│   │   ├── api.ts           # Fetch wrapper for real backend
│   │   ├── mockData.ts      # Faker-based mock data generators
│   │   └── mockApi.ts       # Mock endpoint implementations
│   └── .env.local           # Frontend config (gitignored)
├── tests/                    # Python unit tests
└── pyproject.toml           # Poetry dependencies & config
```

---

## 🐛 Troubleshooting

### Backend Won't Start

```bash
# 1. Check Poetry environment
poetry shell
poetry env info

# 2. Verify Python version
python --version  # Must be ≥3.10

# 3. Reinstall dependencies
poetry lock --no-update
poetry install

# 4. Check if port 8000 is in use
# Windows:
netstat -ano | findstr :8000
# If in use, kill the process or change port:
fastapi dev src/argus/api/main.py --host 127.0.0.1 --port 8001
```

### Frontend Won't Install

```bash
# 1. Clear Bun cache
bun pm cache rm

# 2. Delete node_modules and lock file
rm -r node_modules
rm bun.lockb

# 3. Reinstall
bun install

# 4. Check Node/Bun versions
bun --version
```

### Mock Data Mode Not Working

```bash
# 1. Check .env.local has correct setting
cat web/.env.local | grep NEXT_PUBLIC_MOCK_API

# 2. Must be 'true' (string), not true (boolean)
NEXT_PUBLIC_MOCK_API=true

# 3. Rebuild frontend
cd web
bun run build
bun run dev
```

### Supabase Connection Fails

```bash
# 1. Verify credentials in .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...

# 2. Test connectivity
# Visit: https://your-project.supabase.co/auth/v1/health

# 3. Check RLS policies in Supabase Dashboard
# Ensure your JWT can read/write necessary tables
```

---

## 📚 Key Commands Reference

| Task                           | Command                                                   |
| ------------------------------ | --------------------------------------------------------- |
| **Backend: Install deps**      | `cd /; poetry install`                                    |
| **Backend: Start server**      | `poetry shell; fastapi dev src/argus/api/main.py`         |
| **Backend: Run tests**         | `poetry shell; pytest`                                    |
| **Backend: Format & lint**     | `poetry shell; ruff format .; ruff check .`               |
| **Frontend: Install deps**     | `cd web; bun install`                                     |
| **Frontend: Start dev server** | `cd web; bun run dev`                                     |
| **Frontend: Build for prod**   | `cd web; bun run build`                                   |
| **Frontend: Run tests**        | `cd web; bun test`                                        |
| **Frontend: Format code**      | `cd web; bun run format`                                  |
| **Frontend: Lint code**        | `cd web; bun run lint`                                    |
| **Mock API toggle**            | Edit `web/.env.local` → `NEXT_PUBLIC_MOCK_API=true/false` |

---

## ✅ Success Indicators

You'll know everything is working when:

- ✅ Backend server starts with no errors: `Uvicorn running on http://127.0.0.1:8000`
- ✅ API docs accessible: http://localhost:8000/docs (interactive Swagger)
- ✅ Frontend builds without errors: `ready on http://localhost:3000`
- ✅ Landing page loads at http://localhost:3000
- ✅ Tests pass: `pytest` (backend) and `bun test` (frontend) return 0 failures

---

## 🚀 Next Steps

Once everything is running:

1. **Backend Agent Tasks:**
   - Implement 13 API endpoints (auth, strategies, backtests, history)
   - Connect to Supabase with RLS
   - Integrate Alpaca market data
   - Implement quota/rate-limiting middleware

2. **Frontend Agent Tasks:**
   - Build strategy builder form
   - Integrate with real API (replace mock mode)
   - Implement equity curve visualization (Recharts)
   - Add cursor-based pagination for history

3. **Database Tasks:**
   - Create Supabase migrations (profiles, strategies, simulations, features tables)
   - Set up RLS policies
   - Configure monthly quota reset cron

---

## 📞 Support

For issues or questions:

- Check Bun docs: https://bun.sh/docs
- Check Poetry docs: https://python-poetry.org/docs/
- Check Next.js docs: https://nextjs.org/docs
- Check FastAPI docs: https://fastapi.tiangolo.com/
