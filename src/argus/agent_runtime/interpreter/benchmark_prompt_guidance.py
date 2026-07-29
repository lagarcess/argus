from __future__ import annotations

# Benchmark-language slice of the interpreter contract. Kept beside the other
# interpreter helpers so the classification rule and the corridor that
# consumes comparison_baseline evolve together.
BENCHMARK_LANGUAGE_GUIDANCE = (
    "Benchmark language matters in any user language: when a symbol is "
    "framed as a benchmark, reference, comparison target, or market "
    "baseline, put it in comparison_baseline instead of asset_universe. "
    "A one-asset buy/hold request with a separate benchmark is executable "
    "as the primary asset plus comparison_baseline; do not call this an "
    "unsupported direct comparison. Do not add benchmark symbols to "
    "asset_universe unless the user explicitly says to buy, hold, or test "
    "both as traded assets. Examples: AAPL against SPY, AAPL with SPY "
    "as the benchmark, and AAPL con SPY como referencia all mean "
    "asset_universe=['AAPL'] and comparison_baseline='SPY'. "
    "Carry a named comparison target into comparison_baseline verbatim "
    "even when it is a company name with no known or supported symbol; "
    "never silently swap in a default benchmark — validation owns "
    "reporting unsupported ones. 'Compare AAPL with Samsung' and 'comparar "
    "AAPL con Samsung' mean asset_universe=['AAPL'] and "
    "comparison_baseline='Samsung', not 'SPY'. The same holds inside "
    "benchmark phrasings: 'with Nintendo as the benchmark' and 'con "
    "Nintendo como referencia' mean comparison_baseline='Nintendo', "
    "not 'SPY'. "
    "Set field_provenance.comparison_baseline="
    "'explicit_user' only when the current user message explicitly names "
    "the comparison or benchmark. "
)
