ARG MCP_BASE_IMAGE=ghcr.io/leostehlik/llm-wiki-mcp:latest
FROM ${MCP_BASE_IMAGE}

# Private Sovereign Brain overlay for local MCP auth compatibility.
# Keeps upstream llmwiki untouched while supporting local GoTrue HS256 JWTs
# and trusted private-network bearer-token clients.
COPY auth.py /app/auth.py
COPY config.py /app/config.py
COPY server.py /app/server.py
COPY tools/helpers.py /app/tools/helpers.py
