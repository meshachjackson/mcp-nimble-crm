"""Remote (multi-tenant, OAuth-protected) deployment mode for mcp-nimble-crm.

Everything in this package is only imported when the server runs as a hosted
claude.ai custom connector. The stdio path never touches it and never needs
the `remote` optional dependencies.
"""
