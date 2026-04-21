class DraftingError(Exception):
    """Exception raised when strategy drafting fails (e.g. LLM failure or quota issues)."""

    pass
