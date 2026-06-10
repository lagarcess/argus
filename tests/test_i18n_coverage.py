import json
import re
from pathlib import Path
from typing import Any, Dict, Set

import pytest

# Paths
LOCALES_DIR = Path("web/public/locales")
BASE_LOCALE = "en"

# Known missing translations that are non-trivial to fix automatically.
# Format: {(locale, file_name, key): {"reason": "...", "owner": "product/Codex"}}
KNOWN_I18N_GAPS: Dict[tuple[str, str, str], Dict[str, str]] = {}


def flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "."
) -> Dict[str, str]:
    """Flattens a nested dictionary."""
    items: list[tuple[str, str]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v)))
    return dict(items)


def extract_placeholders(text: str) -> Set[str]:
    """Extracts i18next interpolations like {{count}} and tags like <0>...</0>."""
    if not isinstance(text, str):
        return set()
    curlies = set(re.findall(r"\{\{.+?\}\}", text))
    tags = set(re.findall(r"<\d+>|</\d+>", text))
    return curlies | tags


def get_locales() -> list[str]:
    """Returns a list of all locales found in the locales directory."""
    if not LOCALES_DIR.exists():
        return []
    locales = [d.name for d in LOCALES_DIR.iterdir() if d.is_dir()]
    return sorted(locales)


def test_i18n_valid_json() -> None:
    """Asserts that all locale files are valid JSON."""
    for locale in get_locales():
        locale_dir = LOCALES_DIR / locale
        for json_file in locale_dir.glob("**/*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {json_file}: {e}")


def test_i18n_key_and_placeholder_parity() -> None:
    """Asserts that all locales have the same keys and placeholders as the base locale."""
    base_dir = LOCALES_DIR / BASE_LOCALE
    if not base_dir.exists():
        pytest.skip(f"Base locale '{BASE_LOCALE}' not found.")

    locales = get_locales()
    if len(locales) <= 1:
        pytest.skip("No translated locales found to compare against.")

    # Load base locale files
    base_data: Dict[str, Dict[str, str]] = {}
    for json_file in base_dir.glob("**/*.json"):
        rel_path = json_file.relative_to(base_dir).as_posix()
        with open(json_file, encoding="utf-8") as f:
            base_data[rel_path] = flatten_dict(json.load(f))

    errors: list[str] = []

    for locale in locales:
        if locale == BASE_LOCALE:
            continue

        locale_dir = LOCALES_DIR / locale
        for rel_path, base_keys in base_data.items():
            translated_file = locale_dir / rel_path

            # File existence check
            if not translated_file.exists():
                errors.append(f"[{locale}] Missing entire file: {rel_path}")
                continue

            with open(translated_file, encoding="utf-8") as f:
                translated_keys = flatten_dict(json.load(f))

            base_key_set = set(base_keys.keys())
            translated_key_set = set(translated_keys.keys())

            # Find missing keys
            missing_keys = base_key_set - translated_key_set
            for key in missing_keys:
                gap_id = (locale, rel_path, key)
                if gap_id not in KNOWN_I18N_GAPS:
                    errors.append(f"[{locale}] Missing key in {rel_path}: {key}")

            # Find extra keys
            extra_keys = translated_key_set - base_key_set
            for key in extra_keys:
                errors.append(
                    f"[{locale}] Extra key in {rel_path} (not in {BASE_LOCALE}): {key}"
                )

            # Check placeholders for keys that exist in both
            common_keys = base_key_set & translated_key_set
            for key in common_keys:
                base_text = base_keys[key]
                translated_text = translated_keys[key]

                base_placeholders = extract_placeholders(base_text)
                translated_placeholders = extract_placeholders(translated_text)

                if base_placeholders != translated_placeholders:
                    errors.append(
                        f"[{locale}] Placeholder mismatch in {rel_path} for key '{key}':\n"
                        f"  Expected (from {BASE_LOCALE}): {base_placeholders}\n"
                        f"  Found: {translated_placeholders}"
                    )

    if errors:
        error_msg = "i18n coverage drifts found:\n" + "\n".join(errors)
        pytest.fail(error_msg)
