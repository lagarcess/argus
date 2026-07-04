from __future__ import annotations

from argus.agent_runtime.recovery_messages import resolve_recovery_language

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


def with_response_heading(*, heading: str, body: str | None) -> str:
    """Add lightweight presentation chrome without owning the assistant language."""

    cleaned_heading = " ".join(str(heading or "").split()).strip()
    cleaned_body = str(body or "").strip()
    if not cleaned_heading or not cleaned_body:
        return cleaned_body
    markdown_heading = f"**{cleaned_heading}**"
    if cleaned_body.startswith(markdown_heading) or cleaned_body.startswith("#"):
        return cleaned_body
    return f"{markdown_heading}\n\n{cleaned_body}"


def result_followup_heading(focus: str | None, *, language: str = "en") -> str:
    if resolve_recovery_language(language) == "es-419":
        if focus == "next_experiment":
            return "Qué probar después"
        if focus == "peak_date":
            return "Fecha máxima"
        if focus == "peak_value":
            return "Valor máximo"
        if focus == "drawdown_date":
            return "Fecha de caída"
        if focus == "max_drawdown":
            return "Caída máxima"
        if focus == "result_card_fact":
            return "Dato del resultado"
        if focus == "what_tested":
            return "Qué se probó"
        if focus == "assumptions":
            return "Supuestos"
        return "Qué pasó"
    if focus == "next_experiment":
        return "Try next"
    if focus == "peak_date":
        return "Peak date"
    if focus == "peak_value":
        return "Peak value"
    if focus == "drawdown_date":
        return "Drawdown date"
    if focus == "max_drawdown":
        return "Drawdown"
    if focus == "result_card_fact":
        return "Result fact"
    if focus == "what_tested":
        return "What was tested"
    if focus == "assumptions":
        return "Assumptions"
    return "What happened"
