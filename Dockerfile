FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY mcp_nimble_crm ./mcp_nimble_crm
RUN pip install --no-cache-dir ".[remote]"

# SQLite lives on a mounted volume in production (NIMBLE_MCP_DB=/data/...).
RUN mkdir -p /data
ENV NIMBLE_MCP_DB=/data/nimble-remote.db

EXPOSE 8000
CMD ["mcp-nimble-crm-remote"]
