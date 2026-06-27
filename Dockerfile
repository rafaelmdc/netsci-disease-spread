# Multi-stage build using uv for a fully reproducible, no-manual-install image.
# The same image runs the CLI, notebooks, and every Nextflow process.

FROM python:3.12-slim AS builder

# uv binary from the official distroless image
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies first (cached layer), without the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now install the project (README.md is referenced by pyproject metadata).
COPY README.md ./
COPY src ./src
COPY configs ./configs
COPY vendor ./vendor
RUN uv sync --frozen --no-dev

# --- runtime image: just python + the built venv -------------------------
FROM python:3.12-slim AS runtime

# procps provides `ps`, which Nextflow needs to collect per-task metrics.
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# uv kept available so the notebook service can add tools ephemerally.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

# Artifact dirs (also bind-mounted by docker-compose).
RUN mkdir -p data results figures

ENTRYPOINT ["netsci"]
CMD ["--help"]
