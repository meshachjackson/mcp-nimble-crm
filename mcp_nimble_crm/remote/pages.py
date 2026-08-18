"""Minimal inline HTML for the one-time key setup page. No template deps."""

from __future__ import annotations

import html

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Connect Nimble CRM</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #f5f5f4;
         display: flex; justify-content: center; padding: 3rem 1rem; color: #1c1917; }}
  .card {{ background: #fff; border: 1px solid #e7e5e4; border-radius: 12px;
           padding: 2rem; max-width: 26rem; width: 100%; }}
  h1 {{ font-size: 1.15rem; margin: 0 0 .5rem; }}
  p {{ font-size: .9rem; line-height: 1.45; color: #44403c; }}
  input[type=password] {{ width: 100%; box-sizing: border-box; padding: .6rem .7rem;
           border: 1px solid #d6d3d1; border-radius: 8px; font-size: .95rem; margin: .75rem 0; }}
  button {{ width: 100%; padding: .65rem; border: 0; border-radius: 8px; background: #1c1917;
           color: #fff; font-size: .95rem; cursor: pointer; }}
  .err {{ background: #fef2f2; border: 1px solid #fecaca; color: #991b1b;
          border-radius: 8px; padding: .6rem .8rem; font-size: .85rem; }}
  .hint {{ font-size: .8rem; color: #78716c; }}
</style>
</head>
<body>
<div class="card">
  <h1>Connect Nimble CRM to Claude</h1>
  <p>Paste your personal Nimble API key. It is validated against your Nimble
     account, encrypted, and stored server-side. Claude only ever receives a
     temporary access token, never the key itself.</p>
  <p class="hint">Get a key at app.nimble.com &rarr; Settings &rarr; API.</p>
  {error}
  <form method="post" action="setup">
    <input type="hidden" name="txn" value="{txn}">
    <input type="password" name="api_key" placeholder="Nimble API key"
           autocomplete="off" autofocus required>
    <button type="submit">Validate and connect</button>
  </form>
</div>
</body>
</html>"""

_DONE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family: system-ui; padding: 3rem; text-align: center;">
<h1 style="font-size:1.1rem">{title}</h1><p>{body}</p></body></html>"""


def setup_form(txn: str, error: str | None = None) -> str:
    err_html = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return _PAGE.format(txn=html.escape(txn), error=err_html)


def message_page(title: str, body: str) -> str:
    return _DONE.format(title=html.escape(title), body=html.escape(body))
