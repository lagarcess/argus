# Argus Architecture Decisions

## Core Technologies

- **Frontend:** Next.js 15 + React + TypeScript + Tailwind CSS + shadcn/ui. Built and managed using **Bun**.
  - *Why Bun?* High-performance package manager and JavaScript runtime. Accelerates installation, execution, and testing compared to Node/npm.
- **Backend:** FastAPI (Python 3.10+) managed with **Poetry**.
  - *Why Python & FastAPI?* Exceptional numerical processing ecosystem. FastAPI provides automatic schema validation (Pydantic) and asynchronous endpoint execution.
- **Quantitative Engine:** Numba + VectorBT.
  - *Why Numba?* We compile Python code to native machine instructions for mathematically heavy operations (e.g., structural and harmonic pattern recognition), hitting strict latency SLAs (<3s execution).
  - *Why VectorBT?* Highly optimized vectorized backtesting on large pandas DataFrames.
- **Data Layer:** PostgreSQL (Supabase).
  - *Why Supabase?* Provides PostgREST out-of-the-box, Row-Level Security (RLS) synchronized with JWTs, and Edge Functions.

## Hybrid Data Model (Mock vs. Real)

- *Why Mock Data Layer?* Allows parallel execution by frontend and backend teams. The frontend uses `@faker-js/faker` wrapped in a mock API schema (`NEXT_PUBLIC_MOCK_API=true`), unblocking UI development before full API endpoints are built.
