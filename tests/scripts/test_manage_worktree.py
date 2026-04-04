import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scripts.manage_worktree import app

runner = CliRunner()


@pytest.fixture
def mock_subprocess():
    with patch("scripts.manage_worktree.subprocess.run") as mock:
        yield mock


@pytest.fixture
def mock_shutil():
    with patch("scripts.manage_worktree.shutil") as mock:
        yield mock


@pytest.fixture
def mock_path():
    with patch("scripts.manage_worktree.Path") as mock:
        # Mocking Path(res.stdout.strip()) from get_repo_root
        mock.return_value.name = "crypto-signals"
        # Mocking parent directory for worktrees
        mock.return_value.parent = MagicMock()
        mock.return_value.parent.__truediv__.return_value.exists.return_value = False
        yield mock


def test_create_local_branch(mock_subprocess, mock_shutil, mock_path):
    # Setup mocks
    # 1. git rev-parse --show-toplevel
    # 2. git fetch origin
    # 3. check remote (fail)
    # 4. check local (success)
    # 5. git worktree add
    # 6. poetry install

    """Verify local branch creation via manage_worktree script."""
    mock_subprocess.side_effect = [
        MagicMock(stdout="/repo/crypto-signals\n"),  # get_repo_root
        MagicMock(returncode=0),  # fetch
        subprocess.CalledProcessError(1, "cmd"),  # remote check fail
        MagicMock(returncode=0),  # local check success
        MagicMock(returncode=0),  # worktree add
        MagicMock(returncode=0),  # poetry install
    ]

    result = runner.invoke(app, ["create", "feat/local"])
    assert result.exit_code == 0
    assert "Found local branch 'feat/local'" in result.stdout
    assert "Dependencies installed" in result.stdout


def test_create_remote_branch(mock_subprocess, mock_shutil, mock_path):
    # 1. get_repo_root
    # 2. fetch
    # 3. check remote (success)
    # 4. worktree add with tracking
    # 5. poetry install

    """Verify remote branch creation via manage_worktree script."""
    mock_subprocess.side_effect = [
        MagicMock(stdout="/repo/crypto-signals\n"),
        MagicMock(returncode=0),  # fetch
        MagicMock(returncode=0),  # remote check success
        subprocess.CalledProcessError(
            1, "cmd"
        ),  # local check fail (CRITICAL FIX: script checks local too)
        MagicMock(returncode=0),  # worktree add
        MagicMock(returncode=0),  # poetry install
    ]

    result = runner.invoke(app, ["create", "feat/remote"])
    assert result.exit_code == 0
    assert "Found remote branch 'origin/feat/remote'" in result.stdout


def test_sync_guardrail_success(mock_subprocess):
    # 1. gh run list (success)
    # 2. git fetch
    # 3. git rebase

    """Ensure synchronization proceeds when guardrails pass."""
    gh_response = json.dumps(
        [
            {
                "conclusion": "success",
                "url": "http://github.com/run/1",
                "displayTitle": "Commit Msg",
            }
        ]
    )

    mock_subprocess.side_effect = [
        MagicMock(stdout=gh_response),  # gh run list
        MagicMock(returncode=0),  # fetch
        MagicMock(returncode=0),  # rebase
    ]

    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "Main is healthy" in result.stdout
    assert "Successfully synced" in result.stdout


def test_sync_guardrail_failure(mock_subprocess):
    # 1. gh run list (failure)

    """Ensure synchronization aborts when guardrails fail."""
    gh_response = json.dumps(
        [
            {
                "conclusion": "failure",
                "url": "http://github.com/run/1",
                "displayTitle": "Broken Commit",
            }
        ]
    )

    mock_subprocess.side_effect = [
        MagicMock(stdout=gh_response),
    ]

    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 1
    assert "GUARDRAIL ACTIVATED" in result.stdout
    assert "Main build is currently: failure" in result.stdout


def test_sync_force_override(mock_subprocess):
    # 1. gh run list (failure)
    # 2. fetch
    # 3. rebase

    """Verify synchronization succeeds despite failures if force override is used."""
    gh_response = json.dumps(
        [
            {
                "conclusion": "failure",
                "url": "http://github.com/run/1",
                "displayTitle": "Broken Commit",
            }
        ]
    )

    mock_subprocess.side_effect = [
        MagicMock(stdout=gh_response),
        MagicMock(returncode=0),  # fetch
        MagicMock(returncode=0),  # rebase
    ]

    # Use --force to bypass
    result = runner.invoke(app, ["sync", "--force"])
    assert result.exit_code == 0
    assert "Successfully synced" in result.stdout
