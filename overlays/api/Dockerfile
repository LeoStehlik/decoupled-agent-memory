ARG API_BASE_IMAGE=ghcr.io/leostehlik/llm-wiki-api:latest
FROM ${API_BASE_IMAGE}

COPY main.py /app/main.py
COPY auth.py /app/auth.py
COPY config.py /app/config.py
COPY routes/graph.py /app/routes/graph.py
COPY services/graph.py /app/services/graph.py
COPY services/references.py /app/services/references.py
COPY routes/ws.py /app/routes/ws.py
