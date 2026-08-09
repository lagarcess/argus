"""One asset-identity vocabulary: short names, ticker parts, plain fallback."""

from __future__ import annotations

import pytest
from argus.agent_runtime.asset_identity import (
    asset_label_parts,
    label_from_parts,
    short_display_name,
)


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        ("Netflix, Inc. Common Stock", "Netflix"),
        ("Costco Wholesale Corporation Common Stock", "Costco Wholesale"),
        ("NVIDIA Corporation Common Stock", "NVIDIA"),
        ("The Walt Disney Company", "Walt Disney"),
        ("L3Harris Technologies, Inc.", "L3Harris Technologies"),
        ("Target Corporation", "Target"),
        ("Invesco QQQ Trust, Series 1", "Invesco QQQ Trust, Series 1"),
        # Share classes distinguish real listings, so they survive.
        ("Alphabet Inc. Class C Capital Stock", "Alphabet Inc. Class C Capital Stock"),
        ("Comcast Corporation Class A Common Stock", "Comcast Corporation Class A"),
    ],
)
def test_short_names_strip_listing_boilerplate_only(listing, expected) -> None:
    assert short_display_name(listing) == expected


def test_shortening_never_invents_a_name() -> None:
    # Whatever survives is a prefix of what the resolver returned, so the row
    # can never name a company the catalog did not.
    for listing in (
        "Netflix, Inc. Common Stock",
        "The Walt Disney Company",
        "Apple Inc. Common Stock",
    ):
        short = short_display_name(listing)
        assert listing.lower().startswith(short.lower()) or listing.lower().startswith(
            f"the {short.lower()}"
        )


def test_empty_or_unshortenable_names_fall_back_honestly() -> None:
    assert short_display_name("", symbol="spy") == "SPY"
    assert short_display_name("Inc.", symbol="X") == "Inc."


def test_parts_carry_the_ticker_typed_and_render_plain_text() -> None:
    parts = asset_label_parts([{"symbol": "nflx", "name": "Netflix, Inc. Common Stock"}])
    assert parts == [
        {"type": "text", "value": "Netflix"},
        {"type": "ticker", "value": "NFLX"},
    ]
    assert label_from_parts(parts) == "Netflix (NFLX)"
