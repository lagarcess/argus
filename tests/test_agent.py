import uuid
from unittest.mock import ANY, MagicMock, patch

import pytest
from argus.api.drafter import _StrategyDraftOutput
from argus.api.main import app
from argus.api.schemas import StrategyCreate
from argus.domain.schemas import UserResponse
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_supabase():
    with patch("argus.api.agent.get_supabase_client") as mock:
        client_mock = MagicMock()
        mock.return_value = client_mock

        # Setup successful decrement by default
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


fake_user = UserResponse(
    id=str(uuid.uuid4()),
    email="test@example.com",
    is_admin=False,
)


def override_auth():
    return fake_user


app.dependency_overrides[
    app.dependency_overrides.get("check_rate_limit") or "check_rate_limit"
] = override_auth


def test_draft_strategy_success(mock_supabase, mock_drafter):
    response = client.post("/api/v1/agent/draft", json={"prompt": "YOLO on TSLA"})
    assert response.status_code == 200
    data = response.json()
    assert "draft" in data
    assert data["draft"]["symbols"] == ["TSLA"]
    assert data["ai_explanation"] == "Aggressive long momentum bias on TSLA."

    mock_supabase.rpc.assert_called_with("decrement_ai_draft_quota", {"user_uuid": ANY})
    mock_drafter.assert_called_with("YOLO on TSLA")


@patch("argus.api.agent.retry_with_backoff")
def test_draft_strategy_quota_exhausted(mock_retry, mock_supabase):
    # Ensure retry wrapper just passes through exception for the test
    # Mock the retry loop so it just runs once and raises the actual exception
    def bypass_retry(*args, **kwargs):
        def decorator(func):
            def wrapper(*a, **kw):
                return func(*a, **kw)

            return wrapper

        return decorator

    mock_retry.side_effect = bypass_retry

    rpc_mock = MagicMock()
    rpc_mock.execute.side_effect = Exception("P0001: quota exhausted")
    mock_supabase.rpc.return_value = rpc_mock

    response = client.post("/api/v1/agent/draft", json={"prompt": "YOLO on TSLA"})
    assert response.status_code == 402
    assert "Payment Required" in response.json()["detail"]


@patch("argus.api.drafter.ChatOpenAI")
def test_drafter_primary_model_success(mock_chat_openai):
    from argus.api.drafter import draft_strategy

    mock_llm = MagicMock()
    mock_chat_openai.return_value = mock_llm

    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    expected_output = _StrategyDraftOutput(
        strategy=StrategyCreate(
            name="Test",
            symbols=["AAPL"],
            timeframe="1Day",
            entry_criteria=[],
            exit_criteria=[],
            slippage=0.001,
            fees=0.005,
        ),
        ai_explanation="Explanation",
    )
    mock_structured.invoke.return_value = expected_output

    with patch("argus.api.drafter.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.OPENROUTER_API_KEY.get_secret_value.return_value = "sk-test"
        mock_settings.return_value = settings_mock

        result = draft_strategy("Buy AAPL")
        assert result == expected_output


@patch("argus.api.drafter.ChatOpenAI")
def test_drafter_fallback_model_success(mock_chat_openai):
    from argus.api.drafter import draft_strategy

    mock_llm_primary = MagicMock()
    mock_llm_fallback = MagicMock()
    mock_chat_openai.side_effect = [mock_llm_primary, mock_llm_fallback]

    mock_structured_primary = MagicMock()
    mock_structured_primary.invoke.side_effect = Exception("Primary failed")
    mock_llm_primary.with_structured_output.return_value = mock_structured_primary

    mock_structured_fallback = MagicMock()
    expected_output = _StrategyDraftOutput(
        strategy=StrategyCreate(
            name="Fallback",
            symbols=["MSFT"],
            timeframe="1Day",
            entry_criteria=[],
            exit_criteria=[],
            slippage=0.001,
            fees=0.005,
        ),
        ai_explanation="Fallback explanation",
    )
    mock_structured_fallback.invoke.return_value = expected_output
    mock_llm_fallback.with_structured_output.return_value = mock_structured_fallback

    with patch("argus.api.drafter.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.OPENROUTER_API_KEY.get_secret_value.return_value = "sk-test"
        mock_settings.return_value = settings_mock

        result = draft_strategy("Buy MSFT")
        assert result == expected_output
        assert mock_chat_openai.call_count == 2
