# Local Argus calculation core reuse

## Boundary

The local finance chat reuses a generated, version-pinned copy of Argus's real
typed tool declarations, result-card contracts, presenters and finance
algorithms under `server.argus_core`. Importing this package does not load the
production API, OpenRouter, research providers, settings, dotenv, Supabase or
the backtest runtime. Every included declaration is local, requires no
confirmation and declares zero external calls.

The public imports are:

```python
from server.argus_core.tool_declaration import ToolCatalog
from server.argus_core.calculations import get_calculation_declarations
from server.argus_core.tool_contracts import ToolCall, ToolResultCard

catalog = ToolCatalog(get_calculation_declarations())
declaration = catalog.get("time_value")
outcome = declaration.invoke_sync(arguments)
card = declaration.result_card(
    call=ToolCall(tool_name=declaration.name, call_id=call_id, arguments=arguments),
    outcome=outcome,
    artifact_id=artifact_id,
)
```

The catalog contains `time_value`, `growth_projection`, `bond_value`,
`discounted_cash_flow`, `price_multiple`, `income_yield`, `effective_rate`,
`debt_to_income`, `expense_ratio`, `ranked_comparison` and
`valuation_scenarios`. `calculations.answer_request` is also copied so a local
semantic layer can derive its allowed kinds and argument names from this same
catalog.

Calculations return analytical floats exactly as the Argus core computes them.
Only card presentation rounds money. It reads the decimal count from the shared
`platform.common.CURRENCY_DIGITS` owner, converts through `Decimal(str(value))`,
and quantizes with `ROUND_HALF_UP`. This means JPY displays zero decimal places,
KWD displays three, and a half minor unit rounds away from zero consistently in
answers, repairs, ranked rows and valuation scenarios. A float result is
evidence for a conversation; it cannot become a ledger mutation. A separate
user-confirmed command must convert an explicitly named currency through the
existing Decimal/minor-unit domain owner.

## Provenance and currency

Existing provenance kinds remain readable: `user`, `page`, `market_data`,
`assumption`, `computed` and `not_found`. The local copy adds `account` and
`record`. Each local source requires `date`, `ref` and `currency`:

```json
{
  "kind": "account",
  "date": "2026-09-20",
  "ref": "acct-demo-01",
  "currency": "USD"
}
```

A calculation rejects an account or record source whose currency differs from
the calculation currency. It never converts currencies. Page citations remain
the production shape; calculation presenters do not create research sources,
and their source list stays empty unless a caller supplies real endpoint
evidence elsewhere.

## Generated provenance

Generated from repository base `5430d98d61d815e6c4a2bed60213b411a2bb875e`.
The source owners are:

- `src/argus/domain/tool_declaration.py`
- `src/argus/domain/tool_contracts.py`
- `src/argus/domain/calculations/*.py`
- `src/argus/domain/finance/*.py`
- `ResearchSource` from `src/argus/domain/research/contracts.py`

`scripts/sync_argus_core.py` is the executable synchronization owner. It first
checks every selected canonical source file against the recorded SHA-256 for
the pinned revision. It then applies deterministic namespace changes and the
small local adapters documented below. Each derived file carries a generated
header, and `_generated_manifest.json` records both the source and output
hashes. The check also rejects unexpected importable Python files, while
allowing only the documented root `__init__.py` and `research_contracts.py`
adapters. A changed canonical source, a missing adapter seam, a hand edit, or a
stale generated module makes the check fail.

```bash
# Verify the committed package without writing it.
.venv/bin/python scripts/sync_argus_core.py --check

# Regenerate only after deliberately reviewing a new source revision or adapter.
.venv/bin/python scripts/sync_argus_core.py --write
```

The package root `__init__.py` and reduced `research_contracts.py` are the only
hand-maintained local files. They contain no finance algorithm or declaration.
The reduced research contract avoids bringing Babel, provider, or runtime
configuration into the local app.

Source content SHA-256 values:

| Source | SHA-256 |
| --- | --- |
| `tool_declaration.py` | `815494d3fd5b3e66649f0e2e599b32fea7a1c2d9a0256d7f0c4328234e904388` |
| `tool_contracts.py` | `2de8af20aa10d5daf93cab875a4d80cc3c68a1f93ad034da5d97ce0536fab9ae` |
| calculations manifest | `fa01a8f42b08a0fa4f3ceeca2c702b1d37b5f67407f1898fb003bd6014d5ccb4` |
| finance manifest | `ddc01dea995b3ccd794691e8031f94d80e04bd205dd34c471da4ea0672c82d03` |
| full research contracts source | `690aa6b108f8b26d1a85bb9d0878537dd04e1db1108e30e9af8c1875f431d860` |

The two manifest hashes are SHA-256 over sorted lines in the form
`<file-sha256>  <repository-path>\n`. Their source entries are:

```text
299b8c07e2ea3bbed6fbed3bb78174e31486480cf04774320efbb4dcbeca4041  src/argus/domain/calculations/__init__.py
419c601b7f172da220e4f319379da473a69eaf9dfd63b743220be888201a327d  src/argus/domain/calculations/_shared.py
5da4918a39ada214632046cbf8d3b5ca50c0bc205e0b4114f3e4414479e9fc9f  src/argus/domain/calculations/answer_request.py
c32d8cfc8f4cf8da13e38beb69680512089935cbfcde3befacd053c23b0e25a0  src/argus/domain/calculations/bond_value.py
61a33da81ed751d78b1fb915a03804a5fe34afff63ca79555d732ec7d41c0d35  src/argus/domain/calculations/debt_to_income.py
5374797a066a0c964a0dbf0b5c12e1d8a0160d19bbf1b7c17d3ece07a08a9bba  src/argus/domain/calculations/discounted_cash_flow.py
aef5746f45395b5d8b6d4c42240042b41a09949954228c76b56375fdb4ac4716  src/argus/domain/calculations/effective_rate.py
5c596b7fa5bf893eba14e2eafc75d32be56c8d35eeb73f130e1b79221d5313ca  src/argus/domain/calculations/expense_ratio.py
c5fd869f0857e4a508fc45480a499b7b1746d0510d2f5e6ed19e3de5a3072b28  src/argus/domain/calculations/growth_projection.py
c7908de39db2349c679031090e09ed9faa8140a473b1d969afe6a9d8c6563204  src/argus/domain/calculations/income_yield.py
5ce5ac076813b028070316f455d9369c2e56974c1c6ea383efeec5bb036e6599  src/argus/domain/calculations/price_multiple.py
fc32095d2790d6913fe4a33aaf7d46edfae9f1f96847ce17193cabb24d3a6f71  src/argus/domain/calculations/ranked_comparison.py
da769e7c6a0c099332be90308d14ab77489c525b43c8f9c4c89f603154952987  src/argus/domain/calculations/time_value.py
12c10ddd77c0e13dd348ba7e9fd07a2a81774656c26b1739565f8f0303b16e14  src/argus/domain/calculations/valuation_scenarios.py
b82c4d51b37afd4ab89dfbfce756d48b37cd951bf7a5b011b30affa4013a20c2  src/argus/domain/finance/__init__.py
fae5451f531f1b904e6f74f1865899633e00d120598a1a0fd1dc9732945fa3e3  src/argus/domain/finance/_roots.py
9277ac56d39eb3129d389bfa553867b7672e93c17e2d47f88b5d21e2886abd51  src/argus/domain/finance/bonds.py
ff5353308908989af58dcccd781b61e2674d0fa1c2ef5f473617937d70083ab5  src/argus/domain/finance/comparison.py
13732030468f5e0486f9b02ff449ebe349764cc0ba44b41de199d214a20b4be2  src/argus/domain/finance/dcf.py
579998ffb56144b14b62ff8095b4f8109b716e8422fbd726a1c36e1120045cf4  src/argus/domain/finance/growth.py
629ac09bf8bccc453257bd2eb734f839eacdf089fb3dc77ca82c4958ae2c5007  src/argus/domain/finance/money.py
4d3f9a5473e7c92bb1268a1671163929b229420f730b40db3153139c93418264  src/argus/domain/finance/outcomes.py
e555d55d3f68d066cce544161dc6e30794283278d35c3f4ac13440bc95f41f4e  src/argus/domain/finance/ratios.py
c06bce6bbd145fdf17e318ea2c49e03fd27b9e7f0b87592a5486874227047e17  src/argus/domain/finance/tvm.py
a6eeb5cc20c0e9630793af6b4e7dcbc76890568a5527943f8cabab4910d80292  src/argus/domain/finance/valuation.py
```

## Deliberate adaptations

- Imports point at `server.argus_core`; production `argus` modules are never
  imported by the local package.
- The production `loguru` call is adapted to Python's standard `logging`, so the
  local package does not add a logging dependency.
- The full research contract and its Babel/provider dependencies are replaced
  by the exact immutable `ResearchSource` fields tool cards need.
- Babel-backed global currency discovery is replaced by the local app's shared
  `CURRENCY_DIGITS` catalog. Money presenters, including ranked money rows and
  valuation scenarios, derive their decimal places from that same owner.
- `ToolFactSource` adds dated account/record references and the shared
  calculation argument base rejects cross-currency record composition.
- Import ordering was formatted for the local package. Finance algorithms,
  declaration policies, validation rules, unknown retention, result models and
  calculation descriptions otherwise remain the copied implementation.

## Verification

`tests/test_argus_core_reuse.py` executes a representative known result through
every declaration, checks the complete catalog, retained unknown behavior,
result-card serialization, old and new provenance, cross-currency rejection,
positive and negative JPY/KWD half-unit presentation across answers, repairs,
ranked rows and scenarios, and a clean subprocess import with network
connections blocked and no inherited secrets. It also regenerates into a
temporary directory, verifies the result, proves a hand edit and an unexpected
importable module are rejected, and checks the committed package against the
pinned source.
