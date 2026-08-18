"""OAuth authorization-server provider bridging the MCP SDK to RemoteStore.

The SDK (mcp.server.auth) owns the protocol surface: /.well-known metadata,
dynamic client registration, PKCE verification, and the /token endpoint. This
provider owns only state: where clients, codes, and tokens live, and how a
user's encrypted Nimble key rides along with them.

The one non-standard step is authorize(): instead of a login page, the user
lands on /setup and pastes their personal Nimble API key once. The key is
validated live against the Nimble API, encrypted, and bound to the
authorization code; every token descended from that code carries it.
"""

from __future__ import annotations

import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from .storage import RemoteStore, new_token

ACCESS_TOKEN_TTL = 3600           # 1 hour
REFRESH_TOKEN_TTL = 90 * 86400    # 90 days
SCOPE = "nimble"


class NimbleAccessToken(AccessToken):
    """AccessToken carrying the owner's encrypted Nimble key."""

    enc_key: bytes


class NimbleAuthProvider:
    def __init__(self, store: RemoteStore, public_url: str):
        self.store = store
        self.public_url = public_url.rstrip("/")

    # -- client registry (DCR) ---------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        data = self.store.get_client(client_id)
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.store.save_client(client_info.client_id, client_info.model_dump(mode="json"))

    # -- authorization ------------------------------------------------------

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        txn_id = self.store.create_txn(
            client.client_id,
            {
                "state": params.state,
                "scopes": params.scopes or [SCOPE],
                "code_challenge": params.code_challenge,
                "redirect_uri": str(params.redirect_uri),
                "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                "resource": params.resource,
            },
        )
        return f"{self.public_url}/setup?txn={txn_id}"

    def complete_setup(self, txn_id: str, api_key: str) -> str:
        """Called by the /setup page after the pasted key validated live.

        Consumes the single-use txn, mints the authorization code with the
        encrypted key attached, and returns the redirect URL back to Claude.
        """
        txn = self.store.consume_txn(txn_id)
        if txn is None:
            raise AuthorizeError(
                error="access_denied",
                error_description="This setup link expired or was already used.",
            )
        params = txn["params"]
        code = new_token("nac")
        self.store.save_auth_code(
            code,
            txn["client_id"],
            self.store.encrypt_key(api_key),
            {
                "scopes": params["scopes"],
                "code_challenge": params["code_challenge"],
                "redirect_uri": params["redirect_uri"],
                "redirect_uri_provided_explicitly": params["redirect_uri_provided_explicitly"],
                "resource": params.get("resource"),
            },
        )
        return construct_redirect_uri(params["redirect_uri"], code=code, state=params["state"])

    # -- code exchange ------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        loaded = self.store.load_auth_code(authorization_code)
        if loaded is None:
            return None
        _, data = loaded
        if not data:
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=data["scopes"],
            expires_at=time.time() + 60,  # already TTL-gated by the store
            client_id=client.client_id,
            code_challenge=data["code_challenge"],
            redirect_uri=AnyUrl(data["redirect_uri"]),
            redirect_uri_provided_explicitly=data["redirect_uri_provided_explicitly"],
            resource=data.get("resource"),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ):
        from mcp.shared.auth import OAuthToken

        loaded = self.store.load_auth_code(authorization_code.code)
        if loaded is None:
            raise TokenError(error="invalid_grant", error_description="unknown code")
        enc_key, _ = loaded
        self.store.delete_auth_code(authorization_code.code)

        access = new_token("nat")
        refresh = new_token("nrt")
        now = time.time()
        self.store.save_token(
            access, "access", client.client_id, enc_key,
            authorization_code.scopes, None, now + ACCESS_TOKEN_TTL,
        )
        self.store.save_token(
            refresh, "refresh", client.client_id, enc_key,
            authorization_code.scopes, None, now + REFRESH_TOKEN_TTL,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=refresh,
            scope=" ".join(authorization_code.scopes),
        )

    # -- refresh ------------------------------------------------------------

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        row = self.store.load_token(refresh_token, "refresh")
        if row is None or row["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=row["client_id"],
            scopes=row["scopes"],
            expires_at=int(row["expires_at"]) if row["expires_at"] else None,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ):
        from mcp.shared.auth import OAuthToken

        row = self.store.load_token(refresh_token.token, "refresh")
        if row is None:
            raise TokenError(error="invalid_grant", error_description="unknown refresh token")
        # Rotation: the old refresh token dies with this exchange.
        self.store.delete_token(refresh_token.token)

        granted = scopes or refresh_token.scopes
        access = new_token("nat")
        new_refresh = new_token("nrt")
        now = time.time()
        self.store.save_token(
            access, "access", client.client_id, row["enc_key"],
            granted, row["subject"], now + ACCESS_TOKEN_TTL,
        )
        self.store.save_token(
            new_refresh, "refresh", client.client_id, row["enc_key"],
            granted, row["subject"], now + REFRESH_TOKEN_TTL,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=new_refresh,
            scope=" ".join(granted),
        )

    # -- resource-server side ------------------------------------------------

    async def load_access_token(self, token: str) -> NimbleAccessToken | None:
        row = self.store.load_token(token, "access")
        if row is None:
            return None
        return NimbleAccessToken(
            token=token,
            client_id=row["client_id"],
            scopes=row["scopes"],
            expires_at=int(row["expires_at"]) if row["expires_at"] else None,
            enc_key=row["enc_key"],
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.store.delete_token(token.token)
