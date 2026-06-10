import json
import re
from pathlib import Path
from typing import Any

import pytest

# Paths
LOCALES_DIR = Path("web/public/locales")
BASE_LOCALE = "en"

# Known missing translations that are non-trivial to fix automatically.
# Format: {(locale, file_name, key): {"reason": "...", "owner": "product/Codex"}}
KNOWN_I18N_GAPS: dict[tuple[str, str, str], dict[str, str]] = {}


def flatten_dict(value: Any, parent_key: str = "", sep: str = ".") -> dict[str, str]:
    """Flatten nested JSON objects and arrays into comparable path keys."""
    items: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            items.extend(flatten_dict(child, new_key, sep=sep).items())
    elif isinstance(value, list):
        for index, child in enumerate(value):
            new_key = f"{parent_key}[{index}]" if parent_key else f"[{index}]"
            items.extend(flatten_dict(child, new_key, sep=sep).items())
    elif parent_key:
        items.append((parent_key, str(value)))
    return dict(items)


def extract_placeholders(text: str) -> set[str]:
    """Extracts i18next interpolations like {{count}} and tags like <0>...</0>."""
    if not isinstance(text, str):
        return set()
    curlies = {f"{{{{{match.strip()}}}}}" for match in re.findall(r"\{\{(.+?)\}\}", text)}
    tags = set(re.findall(r"<\d+>|</\d+>", text))
    return curlies | tags


def get_locales() -> list[str]:
    """Returns a list of all locales found in the locales directory."""
    if not LOCALES_DIR.exists():
        return []
    locales = [
        d.name for d in LOCALES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]
    return sorted(locales)


def test_i18n_placeholder_extraction_normalizes_interpolation_spacing() -> None:
    base = extract_placeholders("{{count}} <0>{{name}}</0>")
    translated = extract_placeholders("{{ count }} <0>{{ name }}</0>")

    assert translated == base


def test_i18n_flatten_dict_keeps_array_items_distinct() -> None:
    flattened = flatten_dict(
        {"chat": {"placeholder_prompts": ["Test {{count}}", "Review"]}}
    )

    assert flattened == {
        "chat.placeholder_prompts[0]": "Test {{count}}",
        "chat.placeholder_prompts[1]": "Review",
    }


def test_i18n_valid_json() -> None:
    """Asserts that all locale files are valid JSON."""
    if not LOCALES_DIR.exists():
        pytest.fail(f"Locales directory '{LOCALES_DIR}' not found.")

    locales = get_locales()
    if not locales:
        pytest.fail(f"No locale directories found in '{LOCALES_DIR}'.")

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
        pytest.fail(f"Base locale '{BASE_LOCALE}' not found.")

    locales = get_locales()
    if len(locales) <= 1:
        pytest.fail("No translated locales found to compare against.")

    # Load base locale files
    base_data: dict[str, dict[str, str]] = {}
    for json_file in base_dir.glob("**/*.json"):
        rel_path = json_file.relative_to(base_dir).as_posix()
        with open(json_file, encoding="utf-8") as f:
            base_data[rel_path] = flatten_dict(json.load(f))

    if not base_data:
        pytest.fail(
            f"No JSON localization files found in base locale directory '{base_dir}'."
        )

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
