import os
from unittest.mock import MagicMock, patch

from crypto_signals.config import Settings
from crypto_signals.utils.metadata import get_git_hash, get_job_context


def test_get_git_hash_success():
    """Test get_git_hash returns stdout when git command succeeds."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "a1b2c3d\n"
        result = get_git_hash()
        assert result == "a1b2c3d"


def test_get_git_hash_fallback_env():
    """Test get_git_hash uses GIT_SHA env var when git command fails."""
    with (
        patch("subprocess.run", side_effect=FileNotFoundError("No git")),
        patch.dict(os.environ, {"GIT_SHA": "env_hash_123"}),
    ):
        result = get_git_hash()
        assert result == "env_hash_123"


def test_get_git_hash_fallback_commit_sha():
    """Test get_git_hash uses COMMIT_SHA when GIT_SHA is missing."""
    with (
        patch("subprocess.run", side_effect=FileNotFoundError("No git")),
        patch.dict(os.environ, {"COMMIT_SHA": "sha_789"}, clear=True),
    ):
        result = get_git_hash()
        assert result == "sha_789"


def test_get_git_hash_fallback_revision_id():
    """Test get_git_hash uses REVISION_ID when GIT_SHA is missing."""
    with (
        patch("subprocess.run", side_effect=FileNotFoundError("No git")),
        patch.dict(os.environ, {"REVISION_ID": "rev_456"}),
    ):
        # Ensure GIT_SHA is NOT set in this scope (handled by patch.dict if we clear it,
        # but safely we rely on it being overwritten or just not set)
        # Actually patch.dict adds/updates, but doesn't remove unless clear=True.
        # Let's use clear=True to be safe or explicit overwrite
        with patch.dict(os.environ, {}, clear=True):
            os.environ["REVISION_ID"] = "rev_456"
            result = get_git_hash()
            assert result == "rev_456"


def test_get_git_hash_unknown():
    """Test get_git_hash returns unknown when all fail."""
    with (
        patch("subprocess.run", side_effect=FileNotFoundError("No git")),
        patch.dict(os.environ, {}, clear=True),
    ):
        result = get_git_hash()
        assert result == "unknown"


def test_get_job_context():
    """Test get_job_context extracts correct fields."""
    mock_settings = MagicMock(spec=Settings)
    # Setup the return value of model_dump
    expected_context = {
        "ENVIRONMENT": "PROD",
        "TEST_MODE": False,
    }
    mock_settings.model_dump.return_value = expected_context

    context = get_job_context(mock_settings)

    assert context == expected_context

    # Verify model_dump was called with the correct include set
    mock_settings.model_dump.assert_called_once()
    call_kwargs = mock_settings.model_dump.call_args.kwargs
    assert "include" in call_kwargs
    included_fields = call_kwargs["include"]

    # Check for critical fields
    assert "ENVIRONMENT" in included_fields
    assert "TEST_MODE" in included_fields
    assert "RISK_PER_TRADE" in included_fields

    # Check for EXCLUDED fields (Security)
    assert "ALPACA_API_KEY" not in included_fields
    assert "ALPACA_SECRET_KEY" not in included_fields
