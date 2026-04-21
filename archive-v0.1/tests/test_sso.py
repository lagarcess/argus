import pytest
from argus.api.main import app
from argus.config import get_settings
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_settings():
    settings = get_settings()
    original_urls = settings.ALLOWED_REDIRECT_URLS
    settings.ALLOWED_REDIRECT_URLS = [
        "http://localhost:3000/auth/callback",
        "https://argus-app-suz5.onrender.com/auth/callback",
    ]
    yield
    settings.ALLOWED_REDIRECT_URLS = original_urls


# We need to mock the supabase client so it doesn't fail with "Supabase client not configured"
# or try to actually hit the network.
@pytest.fixture(autouse=True)
def mock_supabase_client(monkeypatch):
    class MockRes:
        url = "https://mock.auth.url"

    class MockAuth:
        def sign_in_with_oauth(self, payload):
            return MockRes()

    class MockSupabase:
        auth = MockAuth()

    monkeypatch.setattr("argus.api.main.supabase_client", MockSupabase())


def test_sso_login_valid_local():
    response = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "http://localhost:3000/auth/callback"},
    )
    assert response.status_code == 200
    assert response.json() == {"auth_url": "https://mock.auth.url"}


def test_sso_login_valid_prod():
    response = client.post(
        "/api/v1/auth/sso",
        json={
            "provider": "google",
            "redirect_to": "https://argus-app-suz5.onrender.com/auth/callback",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"auth_url": "https://mock.auth.url"}


def test_sso_login_invalid_domain():
    response = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "https://malicious-site.com"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid redirect URL"


def test_sso_login_phishing_attempt():
    response = client.post(
        "/api/v1/auth/sso",
        json={
            "provider": "google",
            "redirect_to": "https://argus-app-suz5.onrender.com.attacker.com",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid redirect URL"


def test_sso_login_rejects_querystring_redirect():
    response = client.post(
        "/api/v1/auth/sso",
        json={
            "provider": "google",
            "redirect_to": (
                "http://localhost:3000/auth/callback" "?next=https://malicious-site.com"
            ),
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid redirect URL"


def test_sso_login_rejects_empty_redirect():
    response = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": ""},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid redirect URL"


def test_sso_login_rejects_malformed_redirect():
    response = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "not-a-url"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid redirect URL"
