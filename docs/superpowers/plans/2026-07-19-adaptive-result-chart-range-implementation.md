# Adaptive Result-Chart Range Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users explore a completed backtest through adaptive chart ranges, a custom calendar range, visible-range facts, and bounded executed-fill evidence without changing or rerunning the canonical result.

**Architecture:** The backend strategy capability registry resolves optional, generic chart-exploration hints and the chart finalizer records those hints plus marker-cap evidence in the existing immutable chart JSON. A pure frontend policy derives eligible ranges from actual timestamps and resolved hints; `ResultEquityChart` owns only ephemeral viewport state and delegates accessible controls and semantic facts to a focused presentation component.

**Tech Stack:** Python 3.10, Pydantic, Pandas, pytest, TypeScript, React 19, Next.js 16, TradingView Lightweight Charts 5, Bun test, Playwright, i18next.

## Global Constraints

- Start from the clean local integration commit containing this plan; record its exact SHA before editing.
- Read `AGENTS.md`, the five mandatory canon documents, `docs/specs/private-alpha-interim-roadmap.md`, `docs/superpowers/specs/2026-07-19-adaptive-result-chart-range-design.md`, and GitHub issue #250 before changing code.
- Treat `claude/argus-alpha-audit-c2d919` at `f1d03a1d847628e6a8d681b22337ad5fc6c5ebfd` as read-only evidence. Repeat the narrow chart-file comparison, but do not merge or broadly cherry-pick it.
- Default viewport is ALL. Range switching is presentation-only: no refetch, resampling, reinterpretation, persistence, simulation, usage charge, or full-run metric change.
- Candidate presets are `1D`, `1W`, `1M`, `3M`, `YTD`, `1Y`, and `ALL`; show at most four eligible non-ALL presets followed by ALL.
- Actual timestamps decide feasibility. Resolved generic capability hints decide meaningfulness. The frontend receives no strategy name, provider name, or execution-timeframe allowlist.
- Use UTC calendar arithmetic. A month or year is never a fixed millisecond count.
- The accessible event list uses only supplied typed executed-fill markers, never raw signals or backend display-label prose.
- Preserve English and `es-419`, keyboard and touch access, visible focus, light/dark behavior, attribution, tooltips, progressive marker density, result actions, persistence, and reload.
- Do not add a dependency, database migration, endpoint, provider, LLM call, durable viewport preference, chart-library replacement, or unrelated refactor.
- Stop and return to the founder if a migration, public endpoint, runtime/interpreter change, auth/usage change, donor-wide merge, or new dependency appears necessary.
- Follow red-green-refactor for every task. Keep commits atomic and conventional. Never push, merge, deploy, mutate GitHub, or request GPT/Codex review.
- Completion requires Fable's own production-parity local browser QA. Deterministic green alone is not completion.

---

## File Structure

### Backend and contract

- Modify `src/argus/domain/strategy_capabilities.py`: typed internal exploration metadata and one resolver that emits generic chart hints.
- Modify `src/argus/domain/backtesting/charts.py`: attach resolved exploration hints and exact marker-cap evidence to completed chart JSON.
- Modify `tests/test_strategy_capabilities.py`: capability declaration, cadence resolution, safe fallback, and no-display-coupling tests.
- Create `tests/domain/test_result_chart_exploration.py`: chart JSON and marker-cap evidence tests.
- Modify `docs/API_CONTRACT.md`: additive chart JSON contract.
- Modify `docs/DATA_MODEL.md`: immutable optional chart metadata and legacy behavior.

### Frontend policy and presentation

- Create `web/lib/result-chart-range.ts`: pure timestamp normalization, preset eligibility, custom clamping, visible summary, and deterministic event sampling.
- Create `web/__tests__/result-chart-range.test.ts`: all range and summary edge cases.
- Modify `web/components/chat/types.ts`: shared chart metadata types used by chat components.
- Modify `web/lib/argus-api.ts`: matching API hydration types.
- Create `web/components/chat/ResultChartExploration.tsx`: accessible preset/custom controls, visible summary, and bounded event disclosure.
- Modify `web/components/chat/ResultEquityChart.tsx`: chart-instance refs, ephemeral viewport state, and composition with the pure policy and exploration component.
- Modify `web/__tests__/result-equity-chart.test.ts`: interaction wiring and regression guards.
- Modify `web/lib/result-card-playground-fixtures.ts`: long daily, short intraday, periodic, event-heavy, and legacy fixtures.
- Modify `web/__tests__/result-card-playground.test.ts`: fixture and no-network coverage.
- Modify `web/public/locales/en/common.json`: English control, status, summary, event, and validation copy.
- Modify `web/public/locales/es-419/common.json`: equivalent Spanish copy.
- Create `web/e2e/result-chart-range.spec.ts`: deterministic rendered interaction coverage on the dev-only result playground.

Do not create a generic chart framework. `result-chart-range.ts` owns pure policy; `ResultChartExploration.tsx` owns this feature's semantic DOM; `ResultEquityChart.tsx` remains the Lightweight Charts adapter.

---

### Task 1: Resolve Generic Strategy Exploration Hints

**Files:**
- Modify: `src/argus/domain/strategy_capabilities.py`
- Modify: `tests/test_strategy_capabilities.py`

**Interfaces:**
- Consumes: normalized engine config with `template` and `parameters`.
- Produces: `resolve_result_chart_exploration_policy(config: Mapping[str, Any]) -> dict[str, Any]` returning `minimum_visible_observations` and optional `minimum_meaningful_duration` only.

- [ ] **Step 1: Write capability and resolver tests first**

Add tests with these exact behavioral assertions:

```python
from argus.domain.strategy_capabilities import (
    ResultChartExplorationSpec,
    StrategyCapability,
    resolve_result_chart_exploration_policy,
)


def test_buy_and_hold_resolves_one_month_chart_duration():
    assert resolve_result_chart_exploration_policy(
        {"template": "buy_and_hold", "parameters": {}}
    ) == {
        "minimum_visible_observations": 6,
        "minimum_meaningful_duration": "P1M",
    }


@pytest.mark.parametrize(
    ("cadence", "duration"),
    [
        ("daily", "P2D"),
        ("weekly", "P2W"),
        ("biweekly", "P4W"),
        ("monthly", "P2M"),
        ("quarterly", "P6M"),
    ],
)
def test_dca_resolves_two_typed_cadence_cycles(cadence, duration):
    assert resolve_result_chart_exploration_policy(
        {
            "template": "dca_accumulation",
            "parameters": {"dca_cadence": cadence},
        }
    ) == {
        "minimum_visible_observations": 6,
        "minimum_meaningful_duration": duration,
    }


def test_signal_capability_uses_observation_only_policy():
    assert resolve_result_chart_exploration_policy(
        {"template": "rsi_mean_reversion", "parameters": {}}
    ) == {"minimum_visible_observations": 6}


def test_unknown_capability_uses_safe_observation_only_policy():
    assert resolve_result_chart_exploration_policy(
        {"template": "future_strategy", "parameters": {"future_cycle": "fortnight"}}
    ) == {"minimum_visible_observations": 6}


def test_exploration_metadata_contains_no_display_or_provider_fields():
    forbidden = {"display_name", "label", "provider", "asset_class", "timeframe"}
    for capability in STRATEGY_CAPABILITIES.values():
        dumped = capability.result_chart_exploration.model_dump()
        assert forbidden.isdisjoint(dumped)
```

Import `pytest` and retain every existing registry test.

- [ ] **Step 2: Run the new tests and capture the expected red**

Run:

```bash
poetry run pytest tests/test_strategy_capabilities.py -q --no-cov
```

Expected: the new type and resolver imports fail before implementation; existing tests stay green when run without the new tests.

- [ ] **Step 3: Add the typed capability metadata and resolver**

Add an internal type with this public shape:

```python
from collections.abc import Mapping


class ResultChartExplorationSpec(BaseModel):
    minimum_visible_observations: int = Field(default=6, ge=1)
    minimum_meaningful_duration: str | None = None
    cycle_parameter: str | None = None
    cycle_duration_by_value: dict[str, str] = Field(default_factory=dict)
    minimum_visible_cycles: int = Field(default=2, ge=1)


result_chart_exploration: ResultChartExplorationSpec = Field(
    default_factory=ResultChartExplorationSpec
)
```

Insert that field after `fixed_parameters` in the existing
`StrategyCapability`; leave its other fields and validator byte-for-byte
unchanged.

Configure current capabilities in the registry:

```python
result_chart_exploration=ResultChartExplorationSpec(
    minimum_meaningful_duration="P1M"
)
```

for buy-and-hold, and:

```python
result_chart_exploration=ResultChartExplorationSpec(
    cycle_parameter="dca_cadence",
    cycle_duration_by_value={
        "daily": "P1D",
        "weekly": "P1W",
        "biweekly": "P2W",
        "monthly": "P1M",
        "quarterly": "P3M",
    },
    minimum_visible_cycles=2,
)
```

for DCA. Other capabilities intentionally inherit the observation-only default.

Implement the resolver beside the registry. It must scale only the typed one-cycle values declared by the capability; it must not inspect prose or strategy display names:

```python
def _scaled_calendar_duration(duration: str, cycles: int) -> str | None:
    if not duration.startswith("P") or len(duration) < 3:
        return None
    unit = duration[-1]
    if unit not in {"D", "W", "M", "Y"}:
        return None
    try:
        amount = int(duration[1:-1])
    except ValueError:
        return None
    if amount < 1 or cycles < 1:
        return None
    return f"P{amount * cycles}{unit}"


def resolve_result_chart_exploration_policy(
    config: Mapping[str, Any],
) -> dict[str, Any]:
    template = str(config.get("template") or "").strip()
    capability = STRATEGY_CAPABILITIES.get(template)
    spec = (
        capability.result_chart_exploration
        if capability is not None
        else ResultChartExplorationSpec()
    )
    duration = spec.minimum_meaningful_duration
    if spec.cycle_parameter:
        parameters = config.get("parameters")
        parameter_values = parameters if isinstance(parameters, Mapping) else {}
        cycle_value = str(parameter_values.get(spec.cycle_parameter) or "").strip()
        one_cycle = spec.cycle_duration_by_value.get(cycle_value)
        resolved = (
            _scaled_calendar_duration(one_cycle, spec.minimum_visible_cycles)
            if one_cycle
            else None
        )
        if resolved is not None:
            duration = resolved

    policy: dict[str, Any] = {
        "minimum_visible_observations": spec.minimum_visible_observations
    }
    if duration:
        policy["minimum_meaningful_duration"] = duration
    return policy
```

If repository formatting requires wrapping, preserve the signatures and behavior rather than these exact line breaks.

- [ ] **Step 4: Run focused tests and verify green**

Run:

```bash
poetry run pytest tests/test_strategy_capabilities.py tests/test_slot_normalizer.py -q --no-cov
poetry run ruff check src/argus/domain/strategy_capabilities.py tests/test_strategy_capabilities.py
```

Expected: all selected tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit the typed backend policy**

```bash
git add src/argus/domain/strategy_capabilities.py tests/test_strategy_capabilities.py
git commit -m "feat(results): add typed chart exploration policy"
```

---

### Task 2: Persist Generic Policy And Marker-Cap Evidence

**Files:**
- Modify: `src/argus/domain/backtesting/charts.py`
- Create: `tests/domain/test_result_chart_exploration.py`

**Interfaces:**
- Consumes: `resolve_result_chart_exploration_policy(config)` from Task 1 and the complete pre-cap executed-fill marker list.
- Produces: optional-compatible `chart.exploration_policy` and `chart.marker_summary` objects in every new chart payload.

- [ ] **Step 1: Write chart finalization tests first**

Use small deterministic Pandas bars and monkeypatch the signal builder. Include these exact assertions:

```python
def test_result_chart_persists_resolved_exploration_policy(monkeypatch):
    chart = _build_chart(
        monkeypatch,
        template="dca_accumulation",
        parameters={"dca_cadence": "monthly"},
    )
    assert chart["exploration_policy"] == {
        "minimum_visible_observations": 6,
        "minimum_meaningful_duration": "P2M",
    }


def test_result_chart_records_exact_marker_cap_evidence(monkeypatch):
    all_markers = [
        {
            "time": f"2025-01-{(index % 28) + 1:02d}T{index % 24:02d}:00:00",
            "type": "entry" if index % 2 == 0 else "exit",
            "label": "ignored backend display copy",
            "symbols": ["AAPL"],
        }
        for index in range(124)
    ]
    monkeypatch.setattr(charts, "_chart_markers_from_events", lambda _: all_markers)
    chart = _build_chart(monkeypatch)
    assert len(chart["markers"]) == 80
    assert chart["marker_summary"] == {
        "total_groups": 124,
        "included_groups": 80,
        "sampled": True,
    }


def test_uncapped_chart_reports_complete_supplied_marker_set(monkeypatch):
    all_markers = [
        {
            "time": "2025-01-02",
            "type": "entry",
            "label": "Buy AAPL",
            "symbols": ["AAPL"],
        }
    ]
    monkeypatch.setattr(charts, "_chart_markers_from_events", lambda _: all_markers)
    chart = _build_chart(monkeypatch)
    assert chart["marker_summary"] == {
        "total_groups": 1,
        "included_groups": 1,
        "sampled": False,
    }
```

The `_build_chart` test helper must construct a real normalized config and exercise `charts.build_result_chart`; do not test a duplicate production algorithm.

- [ ] **Step 2: Run the new test file and capture the expected red**

```bash
poetry run pytest tests/domain/test_result_chart_exploration.py -q --no-cov
```

Expected: assertions fail because the two chart objects are absent.

- [ ] **Step 3: Attach metadata at the single chart finalization point**

Replace the current immediate thinning with a named pre-cap list:

```python
all_markers = _chart_markers_from_events(events)
markers = _thin_chart_markers(all_markers, limit=80)
chart = {
    "kind": "portfolio_equity",
    "series": series,
    "markers": markers,
    "marker_summary": {
        "total_groups": len(all_markers),
        "included_groups": len(markers),
        "sampled": len(markers) < len(all_markers),
    },
    "exploration_policy": resolve_result_chart_exploration_policy(config),
    "currency": "USD",
    "base_value": series[0]["value"] if series else None,
    "attribution": "TradingView Lightweight Charts",
}
```

Import the Task 1 resolver. Do not change marker grouping, thinning, series values, or `value_summary` behavior.

- [ ] **Step 4: Run chart, engine, and launch regressions**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/domain/test_result_chart_exploration.py \
  tests/domain/test_engine_execution_ledger.py \
  tests/section3/test_engine_simulation.py \
  tests/domain/test_engine_launch.py \
  tests/test_backtest_finalization.py \
  tests/test_supabase_backtest_finalization.py \
  -q --no-cov
poetry run ruff check src/argus/domain/backtesting/charts.py tests/domain/test_result_chart_exploration.py
```

Expected: all selected tests pass without live provider access.

- [ ] **Step 5: Commit chart metadata**

```bash
git add src/argus/domain/backtesting/charts.py tests/domain/test_result_chart_exploration.py
git commit -m "feat(results): persist chart exploration evidence"
```

---

### Task 3: Extend The Additive Chart Contract

**Files:**
- Modify: `web/components/chat/types.ts`
- Modify: `web/lib/argus-api.ts`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `web/lib/result-card-playground-fixtures.ts`
- Modify: `web/__tests__/result-card-playground.test.ts`

**Interfaces:**
- Consumes: backend chart objects from Task 2.
- Produces: matching optional TypeScript shapes with legacy compatibility.

- [ ] **Step 1: Write fixture contract assertions first**

Add one new adaptive fixture with `exploration_policy` and `marker_summary`, while retaining the old persisted fixture without either field. Assert:

```typescript
const adaptive = resultCardPlaygroundFixtures.find(
  (fixture) => fixture.id === "adaptive-intraday-result",
)!.result.chart!;
expect(adaptive.exploration_policy).toEqual({
  minimum_visible_observations: 6,
  minimum_meaningful_duration: "P1M",
});
expect(adaptive.marker_summary).toEqual({
  total_groups: 124,
  included_groups: 80,
  sampled: true,
});
expect(legacyPersistedRunFixture.conversation_result_card.chart).not.toHaveProperty(
  "exploration_policy",
);
```

Generate long fixture series with a deterministic local helper, not hundreds of handwritten entries. The playground must remain static and make no API call.

- [ ] **Step 2: Run the fixture test and capture the expected red**

```bash
cd web
bun test __tests__/result-card-playground.test.ts
```

Expected: the new fixture and type fields do not exist yet.

- [ ] **Step 3: Add identical optional types at both frontend boundaries**

Use these exact structural types in both `types.ts` and `argus-api.ts`:

```typescript
export type ResultChartExplorationPolicy = {
  minimum_visible_observations?: number;
  minimum_meaningful_duration?: string | null;
};

export type ResultChartMarkerSummary = {
  total_groups: number;
  included_groups: number;
  sampled: boolean;
};
```

Extend each `ResultChartPayload`:

```typescript
exploration_policy?: ResultChartExplorationPolicy | null;
marker_summary?: ResultChartMarkerSummary | null;
```

Do not make either field required and do not reject unfamiliar duration strings during hydration.

- [ ] **Step 4: Document the immutable additive contract**

Extend the result chart example and contract notes in `API_CONTRACT.md` with the two objects, their exact meanings, and the statement that range changes do not trigger an API call or change full-run metrics. Extend `DATA_MODEL.md` to state that these optional values live inside existing immutable chart JSON, legacy rows may omit them, and no migration is required.

- [ ] **Step 5: Run fixture, mapping, and build checks**

```bash
cd web
bun test __tests__/result-card-playground.test.ts __tests__/chat-backtest-jobs.test.ts
bun run build
```

Expected: tests and Next.js type checking pass for both new and legacy payloads.

- [ ] **Step 6: Commit the additive contract**

```bash
git add \
  web/components/chat/types.ts \
  web/lib/argus-api.ts \
  web/lib/result-card-playground-fixtures.ts \
  web/__tests__/result-card-playground.test.ts \
  docs/API_CONTRACT.md \
  docs/DATA_MODEL.md
git commit -m "docs(results): extend chart exploration contract"
```

---

### Task 4: Implement The Pure Adaptive Range Policy

**Files:**
- Create: `web/lib/result-chart-range.ts`
- Create: `web/__tests__/result-chart-range.test.ts`

**Interfaces:**
- Consumes: `ResultChartPoint[]`, `ResultChartMarker[]`, and optional generic chart policy/marker summary.
- Produces: eligible range options, validated custom bounds, and visible semantic facts. It imports no React, chart library, API client, strategy type, provider, or localized copy.

- [ ] **Step 1: Write the complete policy matrix first**

Start the file with deterministic UTC generators and these complete behavioral
tests. Add the representative `2h`, `4h`, `6h`, and `12h` cases to the same
table used by the 90-minute test:

```typescript
import { describe, expect, test } from "bun:test";
import {
  deriveResultChartRanges,
  resolveCustomResultChartRange,
  summarizeVisibleResultChartRange,
} from "../lib/result-chart-range";
import type { ResultChartMarker, ResultChartPoint } from "../components/chat/types";

const DAY = 24 * 60 * 60 * 1000;

function timedSeries(start: string, count: number, stepMinutes: number): ResultChartPoint[] {
  const first = Date.parse(start);
  return Array.from({ length: count }, (_, index) => ({
    time: new Date(first + index * stepMinutes * 60_000).toISOString().slice(0, 19),
    value: 1000 + index,
  }));
}

function dailySeries(start: string, count: number): ResultChartPoint[] {
  const first = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: count }, (_, index) => ({
    time: new Date(first + index * DAY).toISOString().slice(0, 10),
    value: 1000 + index,
  }));
}

function keys(series: ResultChartPoint[], duration?: string) {
  return deriveResultChartRanges(series, {
    minimum_visible_observations: 6,
    ...(duration ? { minimum_meaningful_duration: duration } : {}),
  }).map((range) => range.key);
}

test("two-week hourly hold exposes 1D, 1W, and ALL", () => {
  expect(keys(timedSeries("2026-01-01T00:00:00Z", 14 * 24 + 1, 60), "P1M")).toEqual([
    "1D",
    "1W",
    "ALL",
  ]);
});

test("three-year daily hold caps the four shortest meaningful ranges then ALL", () => {
  expect(keys(dailySeries("2023-01-01", 1096), "P1M")).toEqual([
    "1M",
    "3M",
    "YTD",
    "1Y",
    "ALL",
  ]);
});

test("monthly recurring policy suppresses ranges shorter than two months", () => {
  expect(keys(dailySeries("2024-01-01", 731), "P2M")).toEqual([
    "3M",
    "YTD",
    "1Y",
    "ALL",
  ]);
});

test("short run falls back to observation-qualified shorter ranges", () => {
  expect(keys(dailySeries("2026-01-01", 61), "P6M")).toEqual([
    "1D",
    "1W",
    "1M",
    "ALL",
  ]);
});

test.each([90, 120, 240, 360, 720])(
  "unfamiliar or current intraday spacing %s minutes needs no allowlist",
  (stepMinutes) => {
    const count = Math.floor((14 * 24 * 60) / stepMinutes) + 1;
    expect(keys(timedSeries("2026-01-01T00:00:00Z", count, stepMinutes))).toEqual([
      "1D",
      "1W",
      "ALL",
    ]);
  },
);

test("legacy and malformed policies use observation-only behavior", () => {
  const series = dailySeries("2024-01-01", 731);
  const legacy = deriveResultChartRanges(series).map((range) => range.key);
  const malformed = deriveResultChartRanges(series, {
    minimum_visible_observations: 6,
    minimum_meaningful_duration: "one month",
  }).map((range) => range.key);
  expect(malformed).toEqual(legacy);
});

test("YTD anchors to the latest observation and disappears when it duplicates ALL", () => {
  const distinct = deriveResultChartRanges(dailySeries("2025-01-01", 425));
  expect(distinct.map((range) => range.key)).toContain("YTD");
  const duplicate = deriveResultChartRanges(dailySeries("2026-01-01", 60));
  expect(duplicate.map((range) => range.key)).not.toContain("YTD");
});

test("calendar month subtraction clamps to leap day", () => {
  const oneMonth = deriveResultChartRanges(dailySeries("2024-01-01", 91), {
    minimum_visible_observations: 6,
    minimum_meaningful_duration: "P1M",
  }).find((range) => range.key === "1M");
  expect(oneMonth?.startTime).toBe("2024-02-29");
  expect(oneMonth?.endTime).toBe("2024-03-31");
});

test("fewer than six valid points hides every range control", () => {
  expect(deriveResultChartRanges(dailySeries("2026-01-01", 5))).toEqual([]);
});

test("normalization does not rewrite the supplied render series", () => {
  const series = [
    ...dailySeries("2026-01-01", 8),
    { time: "invalid", value: 50 },
    { time: "2026-01-02", value: 999 },
  ];
  const before = JSON.stringify(series);
  deriveResultChartRanges(series);
  expect(JSON.stringify(series)).toBe(before);
});

test("custom dates clamp and include the complete UTC end date", () => {
  const result = resolveCustomResultChartRange(
    timedSeries("2026-01-01T00:00:00Z", 10 * 24, 60),
    "2025-12-01",
    "2027-01-01",
  );
  expect(result.ok).toBe(true);
  if (result.ok) {
    expect(result.range.startTime).toBe("2026-01-01T00:00:00");
    expect(result.range.endTime).toBe("2026-01-10T23:00:00");
  }
});

test("invalid custom input returns typed errors", () => {
  const series = dailySeries("2026-01-01", 10);
  expect(resolveCustomResultChartRange(series, "", "2026-01-03")).toEqual({
    ok: false,
    error: "missing_date",
  });
  expect(resolveCustomResultChartRange(series, "2026-01-04", "2026-01-03")).toEqual({
    ok: false,
    error: "start_after_end",
  });
  expect(resolveCustomResultChartRange(series, "2026-01-03", "2026-01-03")).toEqual({
    ok: false,
    error: "insufficient_observations",
  });
});

test("visible extrema preserve the earliest tied timestamp", () => {
  const summary = summarizeVisibleResultChartRange({
    series: [
      { time: "2026-01-01", value: 10 },
      { time: "2026-01-02", value: 15 },
      { time: "2026-01-03", value: 15 },
      { time: "2026-01-04", value: 5 },
      { time: "2026-01-05", value: 5 },
    ],
    startIndex: 0,
    endIndex: 4,
  });
  expect(summary?.peak).toEqual({ time: "2026-01-02", value: 15 });
  expect(summary?.low).toEqual({ time: "2026-01-04", value: 5 });
});

test("visible events are typed and deterministically capped at twenty", () => {
  const series = dailySeries("2026-01-01", 42);
  const markers: ResultChartMarker[] = series.map((point, index) => ({
    time: point.time,
    type: index % 2 === 0 ? "entry" : "exit",
    label: "prose must not drive accessible copy",
    symbols: ["AAPL"],
  }));
  const summary = summarizeVisibleResultChartRange({
    series,
    markers,
    startIndex: 0,
    endIndex: 41,
  });
  expect(summary?.suppliedEventCount).toBe(42);
  expect(summary?.displayedEvents).toHaveLength(20);
  expect(summary?.displayedEvents[0]?.sourceIndex).toBe(0);
  expect(summary?.displayedEvents.at(-1)?.sourceIndex).toBe(41);
  expect(summary?.eventListSampled).toBe(true);
  expect(summary?.markerSummary).toBeUndefined();
});
```

Add one daily-spacing assertion to the table if it is not already covered by
the long-series tests. Do not pass timeframe or strategy names into production
functions.

- [ ] **Step 2: Run the new policy test and capture the expected red**

```bash
cd web
bun test __tests__/result-chart-range.test.ts
```

Expected: module import failure before implementation.

- [ ] **Step 3: Implement the exact public policy surface**

Export these types and functions:

```typescript
import type {
  ResultChartExplorationPolicy,
  ResultChartMarker,
  ResultChartMarkerSummary,
  ResultChartPoint,
} from "@/components/chat/types";

export type ResultChartRangeKey = "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y" | "ALL";
export type ResultChartSelection = ResultChartRangeKey | "CUSTOM";

export type ResultChartViewport = {
  startIndex: number;
  endIndex: number;
  startTime: string;
  endTime: string;
};

export type ResultChartRangeOption = ResultChartViewport & {
  key: ResultChartRangeKey;
};

export type ResultChartCustomError =
  | "missing_date"
  | "start_after_end"
  | "insufficient_observations";

export type ResultChartCustomResult =
  | { ok: true; range: ResultChartViewport }
  | { ok: false; error: ResultChartCustomError };

export type VisibleResultChartEvent = {
  marker: ResultChartMarker;
  sourceIndex: number;
};

export type VisibleResultChartSummary = {
  startTime: string;
  endTime: string;
  peak: ResultChartPoint;
  low: ResultChartPoint;
  suppliedEventCount: number;
  displayedEvents: VisibleResultChartEvent[];
  eventListSampled: boolean;
  markerSummary?: ResultChartMarkerSummary;
};

export function deriveResultChartRanges(
  series: ResultChartPoint[],
  policy?: ResultChartExplorationPolicy | null,
): ResultChartRangeOption[];

export function resolveCustomResultChartRange(
  series: ResultChartPoint[],
  startDate: string,
  endDate: string,
): ResultChartCustomResult;

export function summarizeVisibleResultChartRange(input: {
  series: ResultChartPoint[];
  markers?: ResultChartMarker[];
  markerSummary?: ResultChartMarkerSummary | null;
  startIndex: number;
  endIndex: number;
  eventLimit?: number;
}): VisibleResultChartSummary | null;
```

Implementation rules:

1. Normalize valid timestamps into a separate sorted/deduplicated index array while leaving the input array untouched.
2. Compute calendar boundaries from the latest valid timestamp in UTC. Clamp month/year subtraction to the last valid day in the target month.
3. Parse only `P<number>D`, `P<number>W`, `P<number>M`, and `P<number>Y`; invalid strings mean no minimum duration.
4. A candidate is data-eligible only if it contains the normalized observation minimum, excludes at least one ALL point, and has distinct bounds.
5. Prefer candidates meeting the meaningful duration, shortest first, capped at four. Use data-eligible fallback only when the complete series is shorter than the meaningful duration. Append ALL.
6. Return an empty option list when fewer than the observation minimum exist; the component still renders the chart.
7. Treat a custom end date as the end of its UTC calendar day. Clamp both inputs to series bounds. A valid custom range contains at least two observations.
8. Derive visible facts from supplied points and typed markers only. Preserve earliest timestamp on equal extrema by replacing only on strict greater/less comparisons.
9. For more than 20 visible markers, choose deterministic evenly spaced source indexes including first and last. Report frontend sampling separately from backend `markerSummary.sampled`.

Do not export duration parsing or add a generic date library.

- [ ] **Step 4: Run the policy matrix and type/build checks**

```bash
cd web
bun test __tests__/result-chart-range.test.ts
bun run build
```

Expected: all policy tests and TypeScript compilation pass.

- [ ] **Step 5: Reassess complexity and commit**

Delete helpers not required by the named matrix. Confirm the module contains no strategy/template/provider/timeframe allowlist, localized copy, React state, fetch, or chart API call.

```bash
git add web/lib/result-chart-range.ts web/__tests__/result-chart-range.test.ts
git commit -m "feat(results): derive adaptive chart ranges"
```

---

### Task 5: Render Accessible Controls And Visible Evidence

**Files:**
- Create: `web/components/chat/ResultChartExploration.tsx`
- Modify: `web/components/chat/ResultEquityChart.tsx`
- Modify: `web/__tests__/result-equity-chart.test.ts`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`

**Interfaces:**
- Consumes: Task 4 options/custom/summary functions and the existing chart instance.
- Produces: localized semantic controls and facts while preserving the canvas chart adapter.

- [ ] **Step 1: Write component wiring and copy tests first**

Extend the Bun tests to assert:

```typescript
expect(source).toContain("deriveResultChartRanges");
expect(source).toContain("resolveCustomResultChartRange");
expect(source).toContain("summarizeVisibleResultChartRange");
expect(source).toContain("setVisibleLogicalRange");
expect(source).toContain("subscribeVisibleLogicalRangeChange");
expect(source).toContain("<ResultChartExploration");
expect(source).not.toContain("buy_and_hold");
expect(source).not.toContain("dca_accumulation");
expect(source).not.toContain("fetch(");
```

Read both locale JSON files and assert every required key exists with a nonempty value. Include keys for presets, Custom, Apply, Cancel, Reset, start/end labels, invalid-range messages, visible-period sentence, peak, low, supplied event count, no displayed events, displayed-event sampling, and backend marker-cap disclosure.

- [ ] **Step 2: Run the focused frontend tests and capture the expected red**

```bash
cd web
bun test __tests__/result-equity-chart.test.ts
```

Expected: the new component, wiring, and locale keys are absent.

- [ ] **Step 3: Implement the focused semantic component**

Use this exact prop boundary:

```typescript
type ResultChartExplorationProps = {
  options: ResultChartRangeOption[];
  selection: ResultChartSelection;
  summary: VisibleResultChartSummary | null;
  currency?: string;
  locale: string;
  customOpen: boolean;
  customError: ResultChartCustomError | null;
  onSelect: (range: ResultChartRangeOption) => void;
  onOpenCustom: () => void;
  onApplyCustom: (startDate: string, endDate: string) => void;
  onCancelCustom: () => void;
  onReset: () => void;
};
```

The component must:

- return `null` for controls when `options` is empty while still permitting a summary if the parent supplies one;
- render preset buttons with `aria-pressed`, a minimum 36-pixel height, visible
  focus, and stable test ids `result-chart-range-1D`,
  `result-chart-range-1W`, `result-chart-range-1M`,
  `result-chart-range-3M`, `result-chart-range-YTD`,
  `result-chart-range-1Y`, and `result-chart-range-ALL` when their options are
  eligible;
- render Custom as an expandable inline calendar form, not a modal or trading-terminal toolbar;
- connect validation copy with `aria-describedby` and preserve entered values after an error;
- render Reset only when selection is not ALL;
- render the visible-period, peak, low, and supplied-event count as normal text;
- render at most the supplied `summary.displayedEvents`, using `marker.type` and `marker.symbols` with localized entry/exit copy, never `marker.label`;
- distinguish “showing N of M supplied events” from “the backend supplied a bounded sample of X total groups”;
- put preset/custom changes in a polite status region, but do not announce continuous pan/zoom updates.

- [ ] **Step 4: Wire ephemeral viewport state into the chart adapter**

In `ResultEquityChart`, keep refs for the chart time scale and a flag identifying programmatic changes. Derive options once from `chart.series` and `chart.exploration_policy`. Initialize selection to ALL whenever the immutable chart payload changes.

For preset selection:

```typescript
programmaticSelectionRef.current = option.key;
timeScaleRef.current?.setVisibleLogicalRange({
  from: option.startIndex,
  to: option.endIndex,
});
setSelection(option.key);
setVisibleIndexes({ from: option.startIndex, to: option.endIndex });
```

For ALL/Reset, call `fitContent()`, set selection to ALL, and restore first/last indexes. For custom, call Task 4 validation before changing the viewport; invalid input leaves the previous range untouched. For visible logical-range notifications, clamp `floor(from)` and `ceil(to)` to data bounds, refresh the summary, and set selection to CUSTOM only when the change was not the matching programmatic range operation.

Do not recreate the chart merely because selection or visible summary changes. Keep the chart construction effect dependent on immutable chart data, locale/theme, marker presentation, and size behavior as required by the existing adapter.

- [ ] **Step 5: Add concise English and Spanish copy**

Put all copy below `chat.result_chart`. Use the established locale structure and plain product language. The English meanings are:

```text
Custom; Apply; Cancel; Reset; Start date; End date;
Choose a start and end date.; Start date must be before end date.;
That range needs at least two observations.;
Visible period: {{start}} to {{end}}.;
Highest visible value; Lowest visible value;
{{count}} displayed executed-fill events in this range.;
No displayed executed-fill events in this range.;
Showing {{shown}} of {{total}} supplied events.;
Argus stored {{included}} of {{total}} executed-fill groups for this result.
```

Translate these naturally into `es-419`; do not leave English fallback copy in the Spanish catalog.

- [ ] **Step 6: Run focused tests, lint, and build**

```bash
cd web
bun test \
  __tests__/result-chart-range.test.ts \
  __tests__/result-equity-chart.test.ts \
  __tests__/result-card-playground.test.ts \
  __tests__/alpha-frontend.test.ts
bun run lint
bun run build
```

Expected: all tests pass, lint has no new errors, and production build succeeds.

- [ ] **Step 7: Commit the accessible chart interaction**

```bash
git add \
  web/components/chat/ResultChartExploration.tsx \
  web/components/chat/ResultEquityChart.tsx \
  web/__tests__/result-equity-chart.test.ts \
  web/public/locales/en/common.json \
  web/public/locales/es-419/common.json
git commit -m "feat(results): add accessible chart range controls"
```

---

### Task 6: Prove Rendered Behavior Deterministically

**Files:**
- Modify: `web/lib/result-card-playground-fixtures.ts`
- Modify: `web/__tests__/result-card-playground.test.ts`
- Create: `web/e2e/result-chart-range.spec.ts`

**Interfaces:**
- Consumes: production `StrategyResultCard` and `ResultEquityChart` components with deterministic fixtures.
- Produces: browser-level evidence for interaction, localization, responsiveness, and zero feature-triggered network activity.

- [ ] **Step 1: Add browser scenarios before final polish**

Use the dev-only result playground and production card component. The semantic
component must expose stable test ids for visible period, peak, low, event
count, event list, custom form, custom start/end, and validation error. Begin
with this complete no-network/full-metric-preservation journey:

```typescript
import { expect, test } from "@playwright/test";

test("adaptive hourly result switches presets, custom range, and reset without network", async ({ page }) => {
  const featureRequests: string[] = [];
  let rangeInteractionStarted = false;
  page.on("request", (request) => {
    if (!rangeInteractionStarted) return;
    const url = new URL(request.url());
    if (url.pathname.includes("/api/") || request.resourceType() === "websocket") {
      featureRequests.push(`${request.method()} ${url.pathname}`);
    }
  });

  await page.goto("/dev/result-card", { waitUntil: "networkidle" });
  const card = page.getByTestId("result-card-fixture-adaptive-intraday-result").first();
  await expect(card.getByText("+12.0%", { exact: true })).toBeVisible();
  await expect(card.getByText("January 1, 2026 to January 15, 2026", { exact: true })).toBeVisible();
  const fullMetric = await card.getByText("+12.0%", { exact: true }).textContent();
  const fullPeriod = await card
    .getByText("January 1, 2026 to January 15, 2026", { exact: true })
    .textContent();

  rangeInteractionStarted = true;
  await card.getByTestId("result-chart-range-1D").click();
  await expect(card.getByTestId("result-chart-range-1D")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(card.getByTestId("result-chart-visible-period")).toContainText("2026");

  await card.getByTestId("result-chart-custom-toggle").click();
  await card.getByTestId("result-chart-custom-start").fill("2026-01-05");
  await card.getByTestId("result-chart-custom-end").fill("2026-01-08");
  await card.getByTestId("result-chart-custom-apply").click();
  await expect(card.getByTestId("result-chart-custom-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await card.getByTestId("result-chart-reset").click();
  await expect(card.getByTestId("result-chart-range-ALL")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(await card.getByText("+12.0%", { exact: true }).textContent()).toBe(fullMetric);
  expect(
    await card
      .getByText("January 1, 2026 to January 15, 2026", { exact: true })
      .textContent(),
  ).toBe(fullPeriod);
  expect(featureRequests).toEqual([]);
});
```

Add four more tests with these exact assertions:

| Test | Required assertions |
| --- | --- |
| Monthly recurring result | `1D`, `1W`, and `1M` are absent under `P2M`; `3M` and ALL are present; full metrics stay unchanged. |
| Legacy payload | the existing old persisted card renders without either optional object, exposes only observation-qualified controls, and Reset never throws. |
| Visible evidence | switching from ALL to `1D` changes visible-period, peak/low, and event count; list length is at most 20; first/last deterministic sampled events match the fixture; backend-cap disclosure is separate. |
| Spanish mobile keyboard | set `i18nextLng` to `es-419` before navigation, use a 390-by-844 viewport, tab through controls, assert visible focus and Spanish names, apply Custom, and assert `<html lang="es-419">`. |

Every test locates one of
`result-card-fixture-adaptive-intraday-result`,
`result-card-fixture-dca-result`,
`result-card-fixture-trade-based-strategy`, or
`result-card-fixture-old-persisted-card-shape`, records API/provider request
counts after initial page load, and asserts the counts do not increase. Extend
the first test so the metric and period comparison runs after preset, Custom,
and Reset rather than only after Reset.

- [ ] **Step 2: Run the e2e file and capture any real rendering failures**

Start the frontend in its supported dev mode, then run:

```bash
cd web
bun run test:e2e -- e2e/result-chart-range.spec.ts
```

Expected before final fixes: tests may expose missing test ids, focus, chart timing, or responsive behavior; they must not be weakened to source-text checks.

- [ ] **Step 3: Make only the bounded interaction corrections required by the red browser tests**

Keep corrections inside the listed chart, exploration, locale, fixture, and test files. Do not modify chat runtime, API routers, auth, usage, persistence, or database code.

- [ ] **Step 4: Run deterministic browser and frontend regression gates**

```bash
cd web
bun run test:e2e -- e2e/result-chart-range.spec.ts
bun test __tests__
bun run lint
bun run build
```

Expected: range e2e passes; all Bun tests pass; no new lint error; build succeeds.

- [ ] **Step 5: Commit deterministic rendered proof**

```bash
git add \
  web/lib/result-card-playground-fixtures.ts \
  web/__tests__/result-card-playground.test.ts \
  web/e2e/result-chart-range.spec.ts \
  web/components/chat/ResultEquityChart.tsx \
  web/components/chat/ResultChartExploration.tsx
git commit -m "test(results): cover chart range journeys"
```

---

### Task 7: Run Fable Self-Review And Production-Parity Local Browser QA

**Files:**
- Modify only if a confirmed acceptance failure requires the smallest correction within the allowed surfaces.

**Interfaces:**
- Consumes: the exact candidate SHA produced by Tasks 1–6 and the user's configured local QA credentials/environment.
- Produces: exact-SHA deterministic evidence, live browser evidence, a complexity reassessment, and a clean local branch ready for independent review.

- [ ] **Step 1: Audit the candidate diff against the approved design before QA**

Run:

```bash
BASE_SHA="$(git merge-base HEAD codex/private-alpha-next)"
git diff --stat "$BASE_SHA"...HEAD
git diff --check "$BASE_SHA"...HEAD
git diff "$BASE_SHA"...HEAD -- \
  src/argus/domain/strategy_capabilities.py \
  src/argus/domain/backtesting/charts.py \
  web/lib/result-chart-range.ts \
  web/components/chat/ResultChartExploration.tsx \
  web/components/chat/ResultEquityChart.tsx
```

Answer in working notes:

1. Does every diff hunk implement a named acceptance criterion?
2. Does any frontend branch inspect strategy, provider, timeframe, prose, label, or language?
3. Does any range action call fetch, simulation, persistence, or usage code?
4. Can the controls be removed while the old chart still renders?
5. Did any helper or abstraction exceed what current behavior and safe fallback require?

Remove or simplify unjustified machinery before continuing. Do not ask GPT, Codex, or a cloud reviewer; this is Fable's own review.

- [ ] **Step 2: Run the complete deterministic candidate gate**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/test_strategy_capabilities.py \
  tests/domain/test_result_chart_exploration.py \
  tests/domain/test_engine_execution_ledger.py \
  tests/section3/test_engine_simulation.py \
  tests/domain/test_engine_launch.py \
  tests/test_backtest_finalization.py \
  tests/test_supabase_backtest_finalization.py \
  tests/agent_runtime \
  tests/test_spine_guardrails.py \
  -q --no-cov
poetry run ruff check \
  src/argus/domain/strategy_capabilities.py \
  src/argus/domain/backtesting/charts.py \
  tests/test_strategy_capabilities.py \
  tests/domain/test_result_chart_exploration.py
cd web
bun test __tests__
bun run lint
bun run build
bun run test:e2e -- e2e/result-chart-range.spec.ts
cd ..
git diff --check
```

Expected: all selected backend/frontend tests and e2e pass; no Ruff error; no new lint error; build and whitespace checks pass. If an unrelated pre-existing failure occurs, record exact reproduction at the base and do not repair it in this lane.

- [ ] **Step 3: Start production-parity local QA on the exact candidate SHA**

Use the repository's supported scripts rather than manually composing backend flags:

Terminal 1:

```bash
.github/qa.sh
```

Terminal 2:

```bash
cd web
bun run dev
```

Confirm `web/.env.local` uses:

```text
NEXT_PUBLIC_MOCK_AUTH=false
NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1
```

Use an existing real-auth persisted completed result where possible. Do not create a new paid backtest merely to obtain fixture data; if no suitable completed result exists, stop and ask the founder before spending provider/model/simulation usage.

- [ ] **Step 4: Perform and record the complete live browser journey yourself**

In the real application, not the dev playground:

1. Log in through rendered real auth and open a persisted completed result.
2. Record the conversation id, run id, candidate SHA, language, viewport, and full-run metric/date text before interaction.
3. Use every eligible preset. Confirm the visible chart and semantic summary change while the full-run metric/date text remains identical.
4. Apply a valid custom range; then attempt missing, reversed, and sub-two-observation ranges and confirm the prior viewport survives each error.
5. Pan and zoom; confirm the selection becomes Custom without repeated screen-reader announcements.
6. Reset to ALL.
7. Inspect peak/low dates and values against the persisted supplied series. Inspect event rows against typed supplied markers and verify both sampling disclosures when applicable.
8. Reload the conversation; confirm the immutable result returns at ALL with unchanged metrics and actions.
9. Repeat in English and Spanish.
10. Repeat at desktop and mobile widths in both light and dark themes.
11. Use browser network inspection to prove range, custom, pan/zoom, and reset caused zero API/provider/simulation/usage/durable-write requests.
12. Capture screenshots of ALL, one short preset, Custom validation, Spanish mobile, and sampled event disclosure.

If any journey fails, reproduce it, write a failing deterministic test when feasible, apply the smallest in-scope correction, rerun the focused gate, and repeat the affected live journey. Do not weaken the requirement or broaden scope.

- [ ] **Step 5: Commit only confirmed QA corrections**

If QA required code changes:

```bash
git add -- \
  src/argus/domain/strategy_capabilities.py \
  src/argus/domain/backtesting/charts.py \
  tests/test_strategy_capabilities.py \
  tests/domain/test_result_chart_exploration.py \
  web/components/chat/types.ts \
  web/components/chat/ResultChartExploration.tsx \
  web/components/chat/ResultEquityChart.tsx \
  web/lib/argus-api.ts \
  web/lib/result-chart-range.ts \
  web/lib/result-card-playground-fixtures.ts \
  web/__tests__/result-chart-range.test.ts \
  web/__tests__/result-equity-chart.test.ts \
  web/__tests__/result-card-playground.test.ts \
  web/e2e/result-chart-range.spec.ts \
  web/public/locales/en/common.json \
  web/public/locales/es-419/common.json \
  docs/API_CONTRACT.md \
  docs/DATA_MODEL.md
git commit -m "fix(results): correct chart range browser behavior"
```

Review `git diff --cached --name-only` before committing and unstage any file
that does not implement the confirmed browser failure. If QA required no
changes, do not create an empty commit.

- [ ] **Step 6: Stop with a clean local handoff report**

The final report must include:

- base SHA, final SHA, branch, worktree path, and `git status --short` result;
- commit list and exact changed-file list;
- donor comparison and whether any hunk was reused;
- red-before-fix evidence per task;
- deterministic test totals and commands;
- live browser QA matrix with conversation/run identifiers redacted to the minimum safe form, screenshots/paths, and network evidence;
- explicit confirmation that full-run metrics, date labels, actions, persistence, reload, auth, and usage did not regress;
- acceptance checklist mapped one-to-one to issue #250;
- complexity reassessment: what was removed or rejected and why;
- remaining gates or blockers;
- explicit statement: nothing pushed, merged, deployed, or mutated on GitHub.

Stop after the clean report. The founder will trigger independent review separately.
