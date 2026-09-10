# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_HTTP_TIMEOUT=300
# ENV UV_HTTP_TIMEOUT=600

# Copy only dependency metadata
COPY pyproject.toml uv.lock ./

# Install only dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

CMD ["/bin/bash"]





# FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# WORKDIR /app

# ENV UV_PROJECT_ENVIRONMENT=/opt/venv
# ENV PATH="/opt/venv/bin:$PATH"

# # Copy only dependency files
# COPY pyproject.toml uv.lock .python-version ./

# # Install dependencies (cached)
# RUN --mount=type=cache,target=/root/.cache/uv \
#     uv sync --frozen --no-dev

# EXPOSE 8000

# CMD ["/bin/bash"]