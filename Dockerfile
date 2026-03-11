FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# Install uv
RUN apt-get update && apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

# Install dependencies using uv
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r pyproject.toml

FROM python:3.12-slim AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install runtime dependencies if needed, e.g. libpq
RUN apt-get update && apt-get install -y libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY . /app/

# Port for Cloud Run and local Uvicorn
EXPOSE 8000

# Default entrypoint using uvicorn
CMD ["uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
