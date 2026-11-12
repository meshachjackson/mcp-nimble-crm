"""SQLite-backed store for OAuth state and encrypted per-user Nimble keys.

Design constraints:
- Nimble API keys are bearer credentials to CRM data. They are encrypted at
  rest with Fernet; the encryption secret lives only in the deploy
  environment, never in this database.
- Access/refresh tokens are stored as SHA-256 hashes, so a leaked database
  alone cannot be replayed against the live service.
- SQLite is deliberate: this serves a small team on one instance. The schema
  is trivial to migrate to Postgres if the tenant count ever justifies it.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS txns (
    txn_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    params TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_codes (
    code_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    enc_key BLOB NOT NULL,
    data TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    token_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('access', 'refresh')),
    client_id TEXT NOT NULL,
    enc_key BLOB NOT NULL,
    scopes TEXT NOT NULL,
    subject TEXT,
    expires_at REAL
);
"""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


class RemoteStore:
    def __init__(self, db_path: str | Path, encryption_key: str):
        self._fernet = Fernet(encryption_key)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._db.commit()

    # -- crypto -----------------------------------------------------------

    def encrypt_key(self, api_key: str) -> bytes:
        return self._fernet.encrypt(api_key.encode())

    def decrypt_key(self, enc_key: bytes) -> str:
        try:
            return self._fernet.decrypt(enc_key).decode()
        except InvalidToken as e:
            raise ValueError(
                "Stored key cannot be decrypted. The encryption secret has "
                "changed; the user must re-authorize."
            ) from e

    # -- housekeeping -----------------------------------------------------

    def _purge_expired(self) -> None:
        now = time.time()
        self._db.execute("DELETE FROM txns WHERE expires_at < ?", (now,))
        self._db.execute("DELETE FROM auth_codes WHERE expires_at < ?", (now,))
        self._db.execute(
            "DELETE FROM tokens WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )

    # -- clients ----------------------------------------------------------

    def save_client(self, client_id: str, data: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO clients VALUES (?, ?, ?)",
                (client_id, json.dumps(data), time.time()),
            )
            self._db.commit()

    def get_client(self, client_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT data FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    # -- pending authorizations (txns) -------------------------------------

    def create_txn(self, client_id: str, params: dict, ttl: float = 600) -> str:
        txn_id = new_token("txn")
        with self._lock:
            self._purge_expired()
            self._db.execute(
                "INSERT INTO txns VALUES (?, ?, ?, ?)",
                (txn_id, client_id, json.dumps(params), time.time() + ttl),
            )
            self._db.commit()
        return txn_id

    def peek_txn(self, txn_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT client_id, params FROM txns WHERE txn_id = ? AND expires_at > ?",
            (txn_id, time.time()),
        ).fetchone()
        if not row:
            return None
        return {"client_id": row[0], "params": json.loads(row[1])}

    def consume_txn(self, txn_id: str) -> dict | None:
        """Single-use: read and delete atomically."""
        with self._lock:
            txn = self.peek_txn(txn_id)
            if txn:
                self._db.execute("DELETE FROM txns WHERE txn_id = ?", (txn_id,))
                self._db.commit()
        return txn

    # -- authorization codes ------------------------------------------------

    def save_auth_code(
        self, code: str, client_id: str, enc_key: bytes, data: dict, ttl: float = 300
    ) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO auth_codes VALUES (?, ?, ?, ?, ?)",
                (_hash(code), client_id, enc_key, json.dumps(data), time.time() + ttl),
            )
            self._db.commit()

    def load_auth_code(self, code: str) -> tuple[bytes, dict] | None:
        row = self._db.execute(
            "SELECT enc_key, data FROM auth_codes WHERE code_hash = ? AND expires_at > ?",
            (_hash(code), time.time()),
        ).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def delete_auth_code(self, code: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM auth_codes WHERE code_hash = ?", (_hash(code),))
            self._db.commit()

    # -- tokens -------------------------------------------------------------

    def save_token(
        self,
        token: str,
        kind: str,
        client_id: str,
        enc_key: bytes,
        scopes: list[str],
        subject: str | None,
        expires_at: float | None,
    ) -> None:
        with self._lock:
            self._purge_expired()
            self._db.execute(
                "INSERT INTO tokens VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_hash(token), kind, client_id, enc_key, json.dumps(scopes), subject, expires_at),
            )
            self._db.commit()

    def load_token(self, token: str, kind: str) -> dict | None:
        row = self._db.execute(
            "SELECT client_id, enc_key, scopes, subject, expires_at FROM tokens "
            "WHERE token_hash = ? AND kind = ? "
            "AND (expires_at IS NULL OR expires_at > ?)",
            (_hash(token), kind, time.time()),
        ).fetchone()
        if not row:
            return None
        return {
            "client_id": row[0],
            "enc_key": row[1],
            "scopes": json.loads(row[2]),
            "subject": row[3],
            "expires_at": row[4],
        }

    def delete_token(self, token: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM tokens WHERE token_hash = ?", (_hash(token),))
            self._db.commit()
