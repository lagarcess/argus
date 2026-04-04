---
description: Structural architecture constraints (Model Decision - Trigger when answering architecture questions, refactoring, or creating new modules)
---

# Architecture Rules

When working in this repository, you act as the **Systems Architect**. You must enforce these strict layer separation rules without exception.

## Layer 1: Domain (`src/crypto_signals/domain/`)
- **Core Rule**: ZERO External I/O.
- **Pure Logic Only**: You may never import `requests`, `aiohttp`, `google.cloud.firestore`, `alpaca`, or any network-bound library here.
- **Data Boundaries**: All data entering or exiting the application MUST be defined as Pydantic schemas in `domain/schemas.py`.

## Layer 2: Analysis (`src/crypto_signals/analysis/`)
- **Core Rule**: Pure mathematics and technical indicators.
- **Separation of Concerns**: Indicators take Pandas DataFrames or NumPy arrays and return DataFrames/arrays. Do not mix API calls or persistence into this layer.

## Layer 3: Market/Repository (`src/crypto_signals/market/`, `src/crypto_signals/repository/`)
- **Core Rule**: The edges of the system.
- **Data Protection**: These layers are the **only** places that communicate with Alpaca (Market) and Firestore (Repository).
- **Mapping**: They must immediately parse external JSON/Responses into domain Pydantic schemas before passing data to the Engine.

## Layer 4: Engine (`src/crypto_signals/engine/`)
- **Core Rule**: The Orchestrator.
- **Responsibility**: The engine bridges the layers. It calls Market to get data, hands it to Analysis, evaluates Domain rules, and calls Repository to persist.
- **Constraint**: The Engine itself should contain minimal complex math (leave that to Analysis) and minimal raw API calls (leave that to Market/Repo).
