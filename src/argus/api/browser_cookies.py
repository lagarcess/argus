"""The single door through which Argus writes cookies to a browser.

Every cookie name is declared in ``COOKIE_REGISTRY`` with the privacy-policy
category that discloses it, and :func:`set_browser_cookie` refuses a name that
is not there. The privacy copy is derived from this registry rather than
inferred by searching for call sites, because a search can only find the
syntactic forms someone thought to look for.

Writing an undisclosed cookie therefore requires bypassing this module on
purpose, which shows up in review, rather than following from ordinary code.
"""

from __future__ import annotations

from typing import Any, Final

# Cookie name -> the item key under legal.privacy.sections.cookies.items that
# discloses it. Adding a cookie means adding it here and to that disclosure.
COOKIE_REGISTRY: Final[dict[str, str]] = {
    "sb-auth-token": "sign_in",
    "sb-refresh-token": "sign_in",
    "argus-guest-handoff": "guest_handoff",
    "argus-guest-handoff-id": "guest_handoff",
}


class UndisclosedCookieError(RuntimeError):
    """Raised when code tries to set a cookie no disclosure covers."""


def _require_registered(name: str) -> None:
    if name not in COOKIE_REGISTRY:
        raise UndisclosedCookieError(
            f"cookie {name!r} is not in COOKIE_REGISTRY, so no privacy "
            "disclosure covers it. Register it and disclose it before setting "
            "it on a browser."
        )


def set_browser_cookie(response: Any, name: str, value: str, **kwargs: Any) -> None:
    """Set a registered cookie. Unregistered names raise rather than ship."""
    _require_registered(name)
    response.set_cookie(name, value, **kwargs)


def delete_browser_cookie(response: Any, name: str, **kwargs: Any) -> None:
    """Delete a registered cookie.

    A delete cannot create browser state, but routing it here keeps one place
    that knows every cookie Argus owns.
    """
    _require_registered(name)
    response.delete_cookie(name, **kwargs)
