"""Environment wiring for remote mode.

server.py calls build_auth_kwargs() while constructing its FastMCP instance
when NIMBLE_MCP_REMOTE is set. That keeps all auth configuration on the
public FastMCP constructor: no monkey-patching, and the stdio path pays no
import cost because this module is only loaded behind the env flag.
"""

from __future__ import annotations

import os

_provider = None
_store = None


class RemoteConfigError(RuntimeError):
    pass


def _require_env(name: str, hint: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RemoteConfigError(f"{name} is required in remote mode. {hint}")
    return value


def public_url() -> str:
    return _require_env(
        "NIMBLE_MCP_PUBLIC_URL",
        "Set it to the public HTTPS base URL of this deployment, "
        "e.g. https://nimble-crm.up.railway.app",
    ).rstrip("/")


def get_store():
    global _store
    if _store is None:
        from .storage import RemoteStore

        _store = RemoteStore(
            db_path=os.environ.get("NIMBLE_MCP_DB", "nimble-remote.db"),
            encryption_key=_require_env(
                "NIMBLE_MCP_ENCRYPTION_KEY",
                'Generate one with: python -c "from cryptography.fernet import '
                "Fernet; print(Fernet.generate_key().decode())\"",
            ),
        )
    return _store


def get_provider():
    global _provider
    if _provider is None:
        from .provider import NimbleAuthProvider

        _provider = NimbleAuthProvider(store=get_store(), public_url=public_url())
    return _provider


def build_auth_kwargs() -> dict:
    """FastMCP constructor kwargs for the OAuth-protected remote server."""
    from mcp.server.auth.settings import (
        AuthSettings,
        ClientRegistrationOptions,
        RevocationOptions,
    )
    from pydantic import AnyHttpUrl

    from .provider import SCOPE

    base = public_url()
    return {
        "auth_server_provider": get_provider(),
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl(base),
            resource_server_url=AnyHttpUrl(f"{base}/mcp"),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=[SCOPE],
                default_scopes=[SCOPE],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[SCOPE],
        ),
        "host": os.environ.get("HOST", "0.0.0.0"),
        "port": int(os.environ.get("PORT", "8000")),
        # Stateless keeps restarts and redeploys invisible to connected
        # clients; every tool call is an independent Nimble REST request.
        "stateless_http": True,
    }
