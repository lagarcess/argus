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
    remaining_ai_draft_quota=5
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
            fees=0.005
        )
        mock.return_value = _StrategyDraftOutput(
            strategy=strategy_create,
            ai_explanation="Aggressive long momentum bias on TSLA."
        )
        yield mock

def test_draft_strategy_success(mock_supabase, mock_drafter):
    response = client.post("/api/v1/agent/draft", json={"prompt": "YOLO on TSLA"})
    assert response.status_code == 200
    data = response.json()
    assert "draft" in data
    assert data["draft"]["symbols"] == ["TSLA"]
    assert data["ai_explanation"] == "Aggressive long momentum bias on TSLA."

    mock_supabase.rpc.assert_called_once_with("decrement_ai_draft_quota", {"user_uuid": fake_user.id})
    mock_drafter.assert_called_once_with("YOLO on TSLA")

def test_draft_strategy_quota_exhausted_real(mock_supabase):
    rpc_mock = MagicMock()
    rpc_mock.execute.side_effect = Exception("P0001: user quota is gone")
    mock_supabase.rpc.return_value = rpc_mock

    response = client.post("/api/v1/agent/draft", json={"prompt": "YOLO on TSLA"})
    assert response.status_code == 402
    data = response.json()
    assert data["detail"]["error"] == "QUOTA_EXCEEDED"

@patch("argus.api.drafter.ChatOpenAI")
def test_drafter_primary_model_success(mock_chat_openai):
    from argus.api.drafter import draft_strategy

    mock_llm = MagicMock()
    mock_chat_openai.return_value = mock_llm

    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    expected_output = _StrategyDraftOutput(
        strategy=StrategyCreate(
            name="Test", symbols=["AAPL"], timeframe="1Day",
            entry_criteria=[], exit_criteria=[], slippage=0.001, fees=0.005
        ),
        ai_explanation="Explanation"
    )
    mock_structured.invoke.return_value = expected_output

    with patch("argus.api.drafter.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.OPENROUTER_API_KEY.get_secret_value.return_value = "sk-test"
        mock_settings.return_value = settings_mock

        result = draft_strategy("Buy AAPL")
        assert result.strategy.symbols == ["AAPL"]
        assert result.ai_explanation == "Explanation"
        assert mock_chat_openai.call_count == 1

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
            name="Fallback", symbols=["MSFT"], timeframe="1Day",
            entry_criteria=[], exit_criteria=[], slippage=0.001, fees=0.005
        ),
        ai_explanation="Fallback explanation"
    )
    mock_structured_fallback.invoke.return_value = expected_output
    mock_llm_fallback.with_structured_output.return_value = mock_structured_fallback

    with patch("argus.api.drafter.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.OPENROUTER_API_KEY.get_secret_value.return_value = "sk-test"
        mock_settings.return_value = settings_mock

        result = draft_strategy("Buy MSFT")
        assert result.strategy.symbols == ["MSFT"]
        assert result.ai_explanation == "Fallback explanation"
        assert mock_chat_openai.call_count == 2
