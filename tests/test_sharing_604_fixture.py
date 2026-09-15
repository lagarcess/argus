"""The standalone fixture must exercise the real conversation list safely."""

import os
import subprocess
import sys


def test_seeded_sharing_conversations_are_listable():
    # Import in a subprocess: this fixture intentionally overrides environment and
    # resets the API singleton. It must not mutate the rest of the test suite.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from scripts.qa.sharing_604_fixture import app, BUNDLES
from fastapi.testclient import TestClient
with TestClient(app) as client:
    response = client.get('/api/v1/conversations')
    assert response.status_code == 200, response.text
    ids = {item['id'] for item in response.json()['items']}
    assert {bundle['conversation']['id'] for bundle in BUNDLES.values()} <= ids
    for bundle in BUNDLES.values():
        candidates = client.get('/api/v1/conversations/' + bundle['conversation']['id'] + '/public-excerpt-candidates').json()['items']
        assert {item['kind'] for item in candidates if item['eligible']} == {'backtest', 'answer', 'research_answer', 'calculation'}
""",
        ],
        env={**os.environ, "PYTHONPATH": "src:.", "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr[-8000:]
