"""Unit tests for the remote OAuth provider and encrypted key store.

No network: key validation is a live-API concern owned by the /setup route
and covered there by an injected failure; everything here is state logic.
"""

import asyncio
import time

import pytest

pytest.importorskip("cryptography")

from cryptography.fernet import Fernet
from mcp.server.auth.provider import AuthorizationParams, AuthorizeError, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from mcp_nimble_crm.remote.provider import NimbleAuthProvider, NimbleAccessToken
from mcp_nimble_crm.remote.storage import RemoteStore

PUBLIC_URL = "https://connector.example.com"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture()
def store(tmp_path):
    return RemoteStore(tmp_path / "test.db", Fernet.generate_key().decode())


@pytest.fixture()
def provider(store):
    return NimbleAuthProvider(store=store, public_url=PUBLIC_URL)


@pytest.fixture()
def client_info():
    return OAuthClientInformationFull(
        client_id="client-abc",
        client_secret=None,
        redirect_uris=[AnyUrl(REDIRECT)],
    )


def _params(state="st4te"):
    return AuthorizationParams(
        state=state,
        scopes=["nimble"],
        code_challenge="challenge123",
        redirect_uri=AnyUrl(REDIRECT),
        redirect_uri_provided_explicitly=True,
        resource=None,
    )


# ---- storage ----------------------------------------------------------------


def test_key_encryption_roundtrip(store):
    enc = store.encrypt_key("NxBsecretkey")
    assert b"NxBsecretkey" not in enc
    assert store.decrypt_key(enc) == "NxBsecretkey"


def test_wrong_secret_cannot_decrypt(tmp_path, store):
    enc = store.encrypt_key("NxBsecretkey")
    other = RemoteStore(tmp_path / "other.db", Fernet.generate_key().decode())
    with pytest.raises(ValueError, match="re-authorize"):
        other.decrypt_key(enc)


def test_tokens_stored_hashed(store):
    store.save_token("nat_raw_value", "access", "c1", store.encrypt_key("k"), ["nimble"], None, None)
    rows = store._db.execute("SELECT token_hash FROM tokens").fetchall()
    assert rows and all("nat_raw_value" not in r[0] for r in rows)
    assert store.load_token("nat_raw_value", "access") is not None
    assert store.load_token("nat_raw_value", "refresh") is None


def test_expired_token_not_loadable(store):
    store.save_token("nat_x", "access", "c1", store.encrypt_key("k"), ["nimble"], None, time.time() - 5)
    assert store.load_token("nat_x", "access") is None


def test_txn_single_use(store):
    txn = store.create_txn("c1", {"a": 1})
    assert store.consume_txn(txn) is not None
    assert store.consume_txn(txn) is None


# ---- provider flow ----------------------------------------------------------


def test_full_authorization_flow(provider, client_info):
    async def flow():
        await provider.register_client(client_info)
        assert (await provider.get_client("client-abc")) is not None

        setup_url = await provider.authorize(client_info, _params())
        assert setup_url.startswith(f"{PUBLIC_URL}/setup?txn=txn_")
        txn = setup_url.split("txn=")[1]

        redirect = provider.complete_setup(txn, "users-nimble-key")
        assert redirect.startswith(REDIRECT)
        assert "state=st4te" in redirect
        code = redirect.split("code=")[1].split("&")[0]

        auth_code = await provider.load_authorization_code(client_info, code)
        assert auth_code is not None
        assert auth_code.code_challenge == "challenge123"

        tokens = await provider.exchange_authorization_code(client_info, auth_code)
        assert tokens.access_token.startswith("nat_")
        assert tokens.refresh_token.startswith("nrt_")

        # Code is single-use.
        assert (await provider.load_authorization_code(client_info, code)) is None

        # The access token carries the encrypted key, decryptable to the original.
        access = await provider.load_access_token(tokens.access_token)
        assert isinstance(access, NimbleAccessToken)
        assert provider.store.decrypt_key(access.enc_key) == "users-nimble-key"
        return tokens

    asyncio.run(flow())


def test_setup_txn_cannot_be_replayed(provider, client_info):
    async def flow():
        await provider.register_client(client_info)
        setup_url = await provider.authorize(client_info, _params())
        txn = setup_url.split("txn=")[1]
        provider.complete_setup(txn, "key-one")
        with pytest.raises(AuthorizeError):
            provider.complete_setup(txn, "key-two")

    asyncio.run(flow())


def test_refresh_rotation(provider, client_info):
    async def flow():
        await provider.register_client(client_info)
        setup_url = await provider.authorize(client_info, _params())
        redirect = provider.complete_setup(setup_url.split("txn=")[1], "k3y")
        code = redirect.split("code=")[1].split("&")[0]
        auth_code = await provider.load_authorization_code(client_info, code)
        first = await provider.exchange_authorization_code(client_info, auth_code)

        rt = await provider.load_refresh_token(client_info, first.refresh_token)
        assert rt is not None
        second = await provider.exchange_refresh_token(client_info, rt, ["nimble"])
        assert second.access_token != first.access_token

        # Old refresh token is dead after rotation.
        assert (await provider.load_refresh_token(client_info, first.refresh_token)) is None
        # New access token still carries the key.
        access = await provider.load_access_token(second.access_token)
        assert provider.store.decrypt_key(access.enc_key) == "k3y"

    asyncio.run(flow())


def test_revocation(provider, client_info):
    async def flow():
        await provider.register_client(client_info)
        setup_url = await provider.authorize(client_info, _params())
        redirect = provider.complete_setup(setup_url.split("txn=")[1], "k")
        code = redirect.split("code=")[1].split("&")[0]
        auth_code = await provider.load_authorization_code(client_info, code)
        tokens = await provider.exchange_authorization_code(client_info, auth_code)

        access = await provider.load_access_token(tokens.access_token)
        await provider.revoke_token(access)
        assert (await provider.load_access_token(tokens.access_token)) is None

    asyncio.run(flow())


def test_unknown_code_exchange_fails(provider, client_info):
    async def flow():
        await provider.register_client(client_info)
        setup_url = await provider.authorize(client_info, _params())
        redirect = provider.complete_setup(setup_url.split("txn=")[1], "k")
        code = redirect.split("code=")[1].split("&")[0]
        auth_code = await provider.load_authorization_code(client_info, code)
        provider.store.delete_auth_code(code)
        with pytest.raises(TokenError):
            await provider.exchange_authorization_code(client_info, auth_code)

    asyncio.run(flow())


# ---- server integration -----------------------------------------------------


def test_key_resolver_routes_to_per_user_client(monkeypatch):
    from mcp_nimble_crm import server

    monkeypatch.setattr(server, "_clients_by_key", {})
    server.set_key_resolver(lambda: "user-a-key")
    try:
        c1 = server._get_client()
        assert c1.api_key == "user-a-key"
        server.set_key_resolver(lambda: "user-b-key")
        c2 = server._get_client()
        assert c2.api_key == "user-b-key"
        assert c1 is not c2
        server.set_key_resolver(lambda: "user-a-key")
        assert server._get_client() is c1  # cached per key
    finally:
        server.set_key_resolver(None)
