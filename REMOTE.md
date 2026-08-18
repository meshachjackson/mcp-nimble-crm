# Hosted deployment: claude.ai custom connector

Run mcp-nimble-crm as a shared remote MCP server so any Claude account
(web, mobile, Desktop, Code) connects to it with two clicks and a one-time
key paste. No per-laptop installs; updates ship by redeploying.

## How auth works

Claude speaks standard OAuth 2.0 (dynamic client registration + PKCE),
served by the MCP SDK's built-in authorization server. The only custom step
is first connect: the user lands on `/setup` and pastes their **personal**
Nimble API key once. The key is:

- validated live against the Nimble API before anything is stored
- encrypted at rest (Fernet) with a secret that exists only in the deploy env
- bound to that user's tokens; every tool call runs against their own key

Claude never sees the key, only short-lived bearer tokens (1 h access,
90-day rotating refresh). Tokens are stored as SHA-256 hashes, so the
database alone is not replayable.

## Deploy on Railway

1. New project → **Deploy from GitHub repo** → this repo. The included
   `railway.json` + `Dockerfile` are picked up automatically.
2. Add a **volume** mounted at `/data` (SQLite lives there).
3. Set variables:

   | Variable | Value |
   |---|---|
   | `NIMBLE_MCP_PUBLIC_URL` | the service's public URL, e.g. `https://<service>.up.railway.app` |
   | `NIMBLE_MCP_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

   `PORT` is injected by Railway; `NIMBLE_MCP_DB` defaults to
   `/data/nimble-remote.db` in the image.
4. Generate a domain (Settings → Networking) and make sure it matches
   `NIMBLE_MCP_PUBLIC_URL` exactly.
5. Check `https://<domain>/healthz` returns `ok`.

Any host that runs a Docker image with a public HTTPS URL works the same
way; Railway is just the reference target.

## Add the connector in Claude

Each user, on their own account:

1. claude.ai → Settings → **Connectors** → **Add custom connector**
2. URL: `https://<domain>/mcp`
3. Click **Connect**: Claude opens the setup page; paste your personal
   Nimble API key (app.nimble.com → Settings → API); done.

On Team/Enterprise plans an Owner can add the connector org-wide; each
member still authorizes individually with their own key, so per-user CRM
permissions are preserved.

Claude Code can use the same deployment:

```bash
claude mcp add --transport http nimble-crm https://<domain>/mcp
```

## Operations

- **Upgrade everyone:** merge to `main`, redeploy. Clients notice nothing
  (the server is stateless per request).
- **Revoke one user:** delete their token rows, or have them disconnect the
  connector; reconnecting re-runs setup.
- **Rotate the encryption secret:** set a new `NIMBLE_MCP_ENCRYPTION_KEY`.
  All stored keys become undecryptable and every user re-authorizes on next
  use. This is the break-glass response to a suspected secret leak.
- **Back up:** the volume file. It contains encrypted keys and hashed
  tokens; it is useless without the env secret, but treat it as sensitive.

## Environment reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `NIMBLE_MCP_PUBLIC_URL` | yes | — | issuer + setup-link base URL |
| `NIMBLE_MCP_ENCRYPTION_KEY` | yes | — | Fernet secret for keys at rest |
| `NIMBLE_MCP_DB` | no | `nimble-remote.db` | SQLite path |
| `PORT` / `HOST` | no | `8000` / `0.0.0.0` | bind address |

## Local smoke test

```bash
pip install -e ".[remote]"
export NIMBLE_MCP_PUBLIC_URL=http://127.0.0.1:8000
export NIMBLE_MCP_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
mcp-nimble-crm-remote
# then: curl http://127.0.0.1:8000/healthz
```

The stdio mode (`mcp-nimble-crm` + `NIMBLE_API_KEY`) is unchanged and needs
none of this.
