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


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        (
            "First Trust Exchange-Traded Fund II First Trust NASDAQ Cybersecurity ETF",
            "First Trust NASDAQ Cybersecurity ETF",
        ),
        (
            "Global X Funds Global X Cybersecurity ETF",
            "Global X Cybersecurity ETF",
        ),
        # No repeated issuer: the resolver's name stands.
        ("SPDR S&P 500 ETF Trust", "SPDR S&P 500 ETF Trust"),
    ],
)
def test_fund_listings_drop_their_repeated_issuer(listing, expected) -> None:
    assert short_display_name(listing) == expected
    # Still a substring of what the resolver returned; nothing invented.
    assert short_display_name(listing) in listing


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        # The defect: a preserved share class blocked the stripper from
        # reaching the legal form in front of it, so this row read
        # "CrowdStrike Holdings, Inc. Class A" beside a clean "Fortinet".
        ("CrowdStrike Holdings, Inc. Class A", "CrowdStrike Class A"),
        ("Alphabet Inc. Class A", "Alphabet Class A"),
        ("Alphabet Inc. Class C", "Alphabet Class C"),
        ("Berkshire Hathaway Inc. Class B", "Berkshire Hathaway Class B"),
        # Nothing to lift off: unchanged.
        ("Fortinet, Inc.", "Fortinet"),
        # Nothing would survive the split, so the name stands whole.
        ("Class A", "Class A"),
    ],
)
def test_share_classes_survive_shortening_without_their_legal_form(
    listing, expected
) -> None:
    assert short_display_name(listing) == expected


def test_share_classes_stay_distinguishable() -> None:
    """The reason share classes are never stripped: they are how two listings
    of the same issuer differ."""
    assert short_display_name("Alphabet Inc. Class A") != short_display_name(
        "Alphabet Inc. Class C"
    )


@pytest.mark.parametrize(
    "listing",
    [
        "CrowdStrike Holdings, Inc. Class A",
        "Alphabet Inc. Class A",
        "Fortinet, Inc.",
        "The Walt Disney Company",
        "First Trust Exchange-Traded Fund II First Trust NASDAQ Cybersecurity ETF",
    ],
)
def test_shortening_never_invents_a_word(listing) -> None:
    """Every surviving word came from the resolver, in its original order."""
    words = short_display_name(listing).split()
    source = [w.strip(",.") for w in listing.split()]
    position = -1
    for word in words:
        position = source.index(word.strip(",."), position + 1)
