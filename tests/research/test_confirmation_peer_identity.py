"""Stored identity survives add, remaining offers and undo without a new lookup."""

from __future__ import annotations

import pytest

from tests.research.test_confirmation_peer_assets import (
    CONFIRMATION_ID,
    _add,
    _client,
    _conversation,
    _in_place_surface_enabled,  # noqa: F401
    _plant_confirmation,
)

CRYPTO_PEERS = [
    {"symbol": "BTC", "name": "Bitcoin", "asset_class": "crypto"},
    {"symbol": "SOL", "name": "Solana", "asset_class": "crypto"},
]


def _selection(peers):
    return {
        "peers": [{"symbol": p["symbol"], "asset_class": p["asset_class"]} for p in peers]
    }


@pytest.mark.parametrize("mode", ["single", "set", "legacy"])
@pytest.mark.parametrize(
    ("asset_class", "subject", "peers"),
    [
        ("crypto", "ETH", CRYPTO_PEERS),
        (
            "equity",
            "AAPL",
            [
                {
                    "symbol": "BTC",
                    "name": "Grayscale Bitcoin Mini Trust ETF",
                    "asset_class": "equity",
                },
                {"symbol": "MSFT", "name": "Microsoft", "asset_class": "equity"},
            ],
        ),
    ],
)
def test_add_row_keeps_the_offered_btc_identity(
    collision_catalog, mode, asset_class, subject, peers
):
    client = _client()
    conversation = _conversation(client)
    metadata = _plant_confirmation(
        client,
        conversation["id"],
        symbols=[subject],
        peers=peers,
        asset_class=asset_class,
    )
    offered = metadata["next_experiments"]["rows"]
    chosen = peers if mode == "set" else peers[:1]
    body = {"symbols": ["BTC"]} if mode == "legacy" else _selection(chosen)
    response = _add(client, conversation["id"], CONFIRMATION_ID, body)
    assert response.status_code == 200, response.text
    result = response.json()["message"]["metadata"]
    assert result["confirmation_payload"]["strategy"]["asset_class"] == asset_class
    assert result["confirmation_payload"]["strategy"]["asset_universe"] == [
        subject,
        *(p["symbol"] for p in chosen),
    ]
    assert result["confirmation_payload"]["launch_payload"]["asset_class"] == asset_class
    assert result["confirmation_card"]["assets_adjustment"]["added"][0] == {
        "symbol": "BTC",
        "name": peers[0]["name"],
    }
    assert offered[0]["why"]["params"]["peers"] == peers[:1]


def test_remaining_and_restored_crypto_rows_keep_the_stored_identity(collision_catalog):
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(
        client,
        conversation["id"],
        symbols=["ETH"],
        peers=CRYPTO_PEERS,
        asset_class="crypto",
    )
    first = _add(
        client, conversation["id"], CONFIRMATION_ID, _selection(CRYPTO_PEERS[1:])
    )
    assert first.status_code == 200, first.text
    rows = first.json()["message"]["metadata"]["next_experiments"]["rows"]
    assert rows[0]["why"]["params"]["peers"] == CRYPTO_PEERS[:1]
    second = _add(
        client, conversation["id"], CONFIRMATION_ID, _selection(CRYPTO_PEERS[:1])
    )
    assert second.status_code == 200, second.text
    restored = _add(
        client, conversation["id"], CONFIRMATION_ID, {"restore_previous": True}
    )
    assert restored.status_code == 200, restored.text
    rows = restored.json()["message"]["metadata"]["next_experiments"]["rows"]
    assert rows[0]["why"]["params"]["peers"] == CRYPTO_PEERS[:1]
    again = _add(
        client, conversation["id"], CONFIRMATION_ID, _selection(CRYPTO_PEERS[:1])
    )
    assert again.status_code == 200, again.text


@pytest.mark.parametrize(
    "peer",
    [
        {"symbol": "BTC", "asset_class": "equity"},
        {"symbol": "AAPL", "asset_class": "crypto"},
    ],
)
def test_client_cannot_change_the_offered_peer_identity(collision_catalog, peer):
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(
        client,
        conversation["id"],
        symbols=["ETH"],
        peers=CRYPTO_PEERS,
        asset_class="crypto",
    )
    response = _add(client, conversation["id"], CONFIRMATION_ID, {"peers": [peer]})
    assert response.status_code == 409, response.text


def test_legacy_stored_row_uses_its_confirmation_class(collision_catalog, monkeypatch):
    from tests.research import test_confirmation_peer_assets as helpers

    compose = helpers.research_peer_add_rows_for_confirmation

    def legacy_rows(*args, **kwargs):
        sidecar = compose(*args, **kwargs)
        for row in sidecar["rows"]:
            row["why"]["params"].pop("peers")
        return sidecar

    monkeypatch.setattr(helpers, "research_peer_add_rows_for_confirmation", legacy_rows)
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(
        client,
        conversation["id"],
        symbols=["ETH"],
        peers=CRYPTO_PEERS,
        asset_class="crypto",
    )
    response = _add(client, conversation["id"], CONFIRMATION_ID, {"symbols": ["BTC"]})
    assert response.status_code == 200, response.text
    payload = response.json()["message"]["metadata"]["confirmation_payload"]
    assert payload["strategy"]["asset_universe"] == ["ETH", "BTC"]
    assert payload["launch_payload"]["asset_class"] == "crypto"
