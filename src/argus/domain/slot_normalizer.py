from typing import Any

from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def normalize_template_name(raw_name: Any) -> str | None:
    """
    Canonicalizes a strategy template name using aliases from the registry.
    Returns the canonical template key or None if not found.
    """
    if not raw_name:
        return None

    clean = str(raw_name).strip().lower()

    # Direct match
    if clean in STRATEGY_CAPABILITIES:
        return clean

    # Alias match
    for template_key, capability in STRATEGY_CAPABILITIES.items():
        # Check primary template key, aliases, and display_name
        aliases = [a.lower() for a in capability.aliases]
        if clean == template_key or clean in aliases or clean == capability.display_name.lower():
            return template_key


    return None

def normalize_parameter_value(template_key: str, param_key: str, raw_value: Any) -> Any:
    """
    Canonicalizes a parameter value using localized aliases from the registry.
    Returns the canonical value if an alias matches, otherwise returns the original value.
    """
    if not raw_value or not template_key or not param_key:
        return raw_value

    capability = STRATEGY_CAPABILITIES.get(template_key)
    if not capability:
        return raw_value

    spec = capability.parameters.get(param_key)
    if not spec:
        return raw_value

    clean_value = str(raw_value).strip().lower()
    res = raw_value

    # 1. Check if it's already a canonical allowed value
    allowed = [str(v).lower() for v in spec.allowed_values]
    if clean_value in allowed:
        # Return the actual allowed value (preserving type if it's in the list)
        for v in spec.allowed_values:
            if str(v).lower() == clean_value:
                res = v
                break
    else:
        # 2. Check value_aliases
        if hasattr(spec, "value_aliases") and spec.value_aliases:
            for canonical_val, aliases in spec.value_aliases.items():
                clean_aliases = [str(a).strip().lower() for a in aliases]
                if clean_value == str(canonical_val).lower() or clean_value in clean_aliases:
                    res = canonical_val
                    break

    return res


