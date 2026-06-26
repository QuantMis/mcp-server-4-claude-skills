# Minimal, single-process image. Compute floor: one idle Python process + a
# SQLite file. Nothing executes between calls.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SKILLS_MCP_HOST=0.0.0.0 \
    SKILLS_MCP_PORT=8080 \
    SKILLS_MCP_DB_PATH=/data/skills.db

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Persist the SQLite file outside the image layer.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

# SKILLS_MCP_BEARER_TOKEN must be supplied at runtime (e.g. via the OAuth
# proxy / secret manager). The server refuses to start without it.
CMD ["python", "-m", "skills_mcp"]
