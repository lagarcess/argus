import uuid
from unittest.mock import MagicMock, patch

import pytest
from argus.api.auth import check_ai_quota
from argus.api.drafter import _StrategyDraftOutput
from argus.api.main import app
from argus.api.schemas import StrategyCreate
from argus.domain.schemas import UserResponse
from fastapi.testclient import TestClient

client = TestClient(app)

fake_user = UserResponse(
    id=str(uuid.uuid4()),
    email="test@example.com",
    is_admin=False,
    remaining_ai_draft_quota=5,
)


def override_auth():
    return fake_user


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[check_ai_quota] = override_auth
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_supabase():
    with patch("argus.api.agent.get_supabase_client") as mock:
        client_mock = MagicMock()
        mock.return_value = client_mock

        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = MagicMock()
        client_mock.rpc.return_value = rpc_mock
        yield client_mock


@pytest.fixture
def mock_drafter():
    with patch("argus.api.agent.draft_strategy") as mock:
        strategy_create = StrategyCreate(
            name="TSLA YOLO",
            symbols=["TSLA"],
            timeframe="1Day",
            entry_criteria=[{"indicator": "Momentum", "operator": ">", "value": 0}],
            exit_criteria=[],
            slippage=0.001,
            fees=0.005,
        )
        mock.return_value = _StrategyDraftOutput(
            strategy=strategy_create,
            ai_explanation="Aggressive long momentum bias on TSLA.",
        )
        yield mock


def test_draft_strategy_success(mock_supabase, mock_drafter):
    response = client.post("/api/v1/agent/draft", json={"prompt": "YOLO on TSLA"})
    assert response.status_code == 200
    data = response.json()
    assert "draft" in data
    assert data["draft"]["symbols"] == ["TSLA"]
    assert data["ai_explanation"] == "Aggressive long momentum bias on TSLA."

    mock_supabase.rpc.assert_called_once_with(
        "decrement_ai_draft_quota", {"user_uuid": fake_user.id}
    )
    mock_drafter.assert_called_once_with("YOLO on TSLA")


def test_draft_strategy_quota_exhausted_real(mock_supabase):
    rpc_mock = MagicMock()
    rpc_mock.execute.side_effect = Exception("P0001: user quota is gone")
    mock_supabase.rpc.return_value = rpc_mock

    response = client.post("/api/v1/agent/draft", json={"prompt": "YOLO on TSLA"})
    assert response.status_code == 402
    data = response.json()
    assert data["detail"]["error"] == "QUOTA_EXCEEDED"


@patch("argus.api.drafter.litellm.completion")
def test_drafter_primary_model_success(mock_completion):
    import json

    from argus.api.drafter import draft_strategy

    mock_response = MagicMock()
    # Provide the JSON string in the mock structure
    mock_response.choices[0].message.content = json.dumps(
        {
            "strategy": {
                "name": "Test",
                "symbols": ["aapl"],
                "timeframe": "1Day",
                "entry_criteria": [],
                "exit_criteria": [],
                "slippage": 0.001,
                "fees": 0.005,
            },
            "ai_explanation": "Explanation",
        }
    )
    mock_completion.return_value = mock_response

    with patch("argus.api.drafter.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.OPENROUTER_API_KEY.get_secret_value.return_value = "sk-test"
        settings_mock.AGENT_MODEL = "test_model"
        mock_settings.return_value = settings_mock

        result = draft_strategy("Buy AAPL")
        # Ensure it was canonicalized
        assert result.strategy.symbols == ["AAPL"]
        assert result.ai_explanation == "Explanation"
        assert mock_completion.call_count == 1
        # assert temperature 0.1
        _, kwargs = mock_completion.call_args
        assert kwargs["temperature"] == 0.1
        assert kwargs["model"] == "test_model"


@patch("argus.api.drafter.litellm.completion")
def test_drafter_fallback_model_success(mock_completion):
    import json

    from argus.api.drafter import draft_strategy

    mock_response_fail = MagicMock()
    mock_response_fail.choices[0].message.content = "Invalid JSON"

    mock_response_success = MagicMock()
    mock_response_success.choices[0].message.content = json.dumps(
        {
            "strategy": {
                "name": "Fallback",
                "symbols": ["msft"],
                "timeframe": "1Day",
                "entry_criteria": [],
                "exit_criteria": [],
                "slippage": 0.001,
                "fees": 0.005,
            },
            "ai_explanation": "Fallback explanation",
        }
    )

    # First call fails parsing (Invalid JSON), second call succeeds
    mock_completion.side_effect = [mock_response_fail, mock_response_success]

    with patch("argus.api.drafter.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.OPENROUTER_API_KEY.get_secret_value.return_value = "sk-test"
        settings_mock.AGENT_MODEL = "primary_model"
        settings_mock.AGENT_FALLBACK_MODEL = "fallback_model"
        mock_settings.return_value = settings_mock

        result = draft_strategy("Buy MSFT")
        assert result.strategy.symbols == ["MSFT"]
        assert result.ai_explanation == "Fallback explanation"
        assert mock_completion.call_count == 2

        # Verify first call
        _, kwargs_primary = mock_completion.call_args_list[0]
        assert kwargs_primary["model"] == "primary_model"

        # Verify second call
        _, kwargs_fallback = mock_completion.call_args_list[1]
        assert kwargs_fallback["model"] == "fallback_model"
