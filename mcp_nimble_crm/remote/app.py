"""Entrypoint for the hosted, multi-tenant deployment.

    mcp-nimble-crm-remote

Run behind HTTPS with these environment variables:
    NIMBLE_MCP_PUBLIC_URL       public base URL (issuer + setup links)
    NIMBLE_MCP_ENCRYPTION_KEY   Fernet key for encrypting stored Nimble keys
    NIMBLE_MCP_DB               SQLite path (default: ./nimble-remote.db)
    PORT / HOST                 bind address (Railway injects PORT)
"""

from __future__ import annotations

import os

import anyio


def main() -> None:
    # Must be set before mcp_nimble_crm.server is imported: the flag makes
    # its FastMCP constructor pick up the OAuth provider and settings.
    os.environ["NIMBLE_MCP_REMOTE"] = "1"

    from starlette.requests import Request
    from starlette.responses import HTMLResponse, RedirectResponse

    from mcp_nimble_crm import server
    from mcp_nimble_crm.client import NimbleClient

    from . import bootstrap, pages

    provider = bootstrap.get_provider()
    store = bootstrap.get_store()

    # Per-request key resolution: the bearer-auth middleware has already
    # verified the token and stashed it in a contextvar by the time any tool
    # body runs. The token carries the caller's encrypted Nimble key.
    def _resolve_key() -> str | None:
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        enc_key = getattr(token, "enc_key", None)
        if enc_key is None:
            return None
        return store.decrypt_key(enc_key)

    server.set_key_resolver(_resolve_key)

    mcp = server.mcp

    @mcp.custom_route("/setup", methods=["GET"])
    async def setup_get(request: Request) -> HTMLResponse:
        txn = request.query_params.get("txn", "")
        if not txn or store.peek_txn(txn) is None:
            return HTMLResponse(
                pages.message_page(
                    "Link expired",
                    "This setup link is invalid or expired. Reconnect the "
                    "Nimble CRM connector from Claude to get a fresh one.",
                ),
                status_code=410,
            )
        return HTMLResponse(pages.setup_form(txn))

    @mcp.custom_route("/setup", methods=["POST"])
    async def setup_post(request: Request):
        form = await request.form()
        txn = str(form.get("txn", ""))
        api_key = str(form.get("api_key", "")).strip()

        if not txn or store.peek_txn(txn) is None:
            return HTMLResponse(
                pages.message_page(
                    "Link expired",
                    "This setup link is invalid or expired. Reconnect from Claude.",
                ),
                status_code=410,
            )

        # Validate the pasted key against the live Nimble API before storing
        # anything. A typo'd key must fail here, not on first tool call.
        def _validate() -> None:
            NimbleClient(api_key=api_key).get_myself()

        try:
            await anyio.to_thread.run_sync(_validate)
        except Exception:
            return HTMLResponse(
                pages.setup_form(
                    txn,
                    error="Nimble rejected that key. Check it at "
                    "app.nimble.com → Settings → API and try again.",
                ),
                status_code=400,
            )

        redirect_url = provider.complete_setup(txn, api_key)
        return RedirectResponse(redirect_url, status_code=302)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> HTMLResponse:
        return HTMLResponse("ok")

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
