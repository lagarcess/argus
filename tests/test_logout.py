from argus.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_logout_clears_cookies():
    # Set a dummy cookie to simulate a logged-in state
    client.cookies.set("sb-access-token", "dummy-token")

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204

    # Check that Set-Cookie header exists and sets the cookie to expire
    set_cookie_headers = (
        response.headers.get_list("set-cookie")
        if hasattr(response.headers, "get_list")
        else response.headers.get_all("set-cookie")
        if hasattr(response.headers, "get_all")
        else [response.headers.get("set-cookie")]
    )

    found_access_token = False
    for header in set_cookie_headers:
        if header and "sb-access-token=" in header:
            found_access_token = True
            assert "Max-Age=0" in header or "expires=" in header.lower()

    assert found_access_token, "sb-access-token cookie was not cleared in the response"
