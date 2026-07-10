from __future__ import annotations

ARGUS_RESPONSE_STYLE_CONTRACT = (
    "Argus response style: sound warm, plain language, concise, and "
    "curiosity-forward. Avoid dense financial PDF tone, long report blocks, "
    "robotic metric dumps, numbered requirements lists, and jargon without "
    "explanation. Prefer one or two short paragraphs; use bullets only for real "
    "choices or next experiments. Let deterministic facts ground the answer, "
    "but let the LLM own natural language. Keep historical-simulation caveats "
    "clear, avoid investment advice, and never make unsupported causal claims "
    "from context packets."
)


def argus_response_style_contract() -> str:
    return ARGUS_RESPONSE_STYLE_CONTRACT


_RESULT_FOLLOWUP_HEADING_KEYS = {
    "next_experiment": "next_experiment",
    "max_drawdown": "max_drawdown",
    "what_tested": "what_tested",
    "assumptions": "assumptions",
}


def result_followup_heading_key(focus: str | None) -> str:
    normalized = str(focus or "").strip()
    return _RESULT_FOLLOWUP_HEADING_KEYS.get(normalized, "general")


def result_followup_response_intent(focus: str | None) -> dict[str, object]:
    normalized = str(focus or "").strip() or "general"
    return {
        "kind": "result_followup_chrome",
        "facts": {
            "focus": normalized,
            "heading_key": result_followup_heading_key(normalized),
        },
    }
