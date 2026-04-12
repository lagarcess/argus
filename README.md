# Argus

High-performance pattern analysis and backtesting engine for trading strategies. Core module powering pivot detection, harmonic pattern recognition, and structural analysis via Numba-optimized algorithms.

## Quick Start & Setup

### Prerequisites
- **Bun** (≥1.0.0)
- **Python** (≥3.10.0)
- **Poetry** (≥1.7.0)

### 1. Install Dependencies

**Backend:**
```bash
poetry install
```

**Frontend:**
```bash
cd web
bun install
```

### 2. Configure Environment

**Backend:**
Copy `.env.example` to `.env` and fill in necessary keys (Supabase, Alpaca).

**Frontend:**
```bash
cp web/.env.example web/.env.local
```
*(Set `NEXT_PUBLIC_MOCK_API=true` to use mock data for frontend development without the backend).*

### 3. Launching the App

**Backend:**
```bash
poetry shell
fastapi dev src/argus/api/main.py
```

**Frontend:**
```bash
cd web
bun run dev
```

For more details on local setup, testing, and mock data usage, see [docs/startup.md](docs/startup.md).
