# Census Tool — dev image: same `uv` resolution as the repo (pyproject + uv.lock).
#
# The virtualenv lives at /opt/census-tool-base/.venv so you can mount the
# project to /workspace without replacing dependencies (common gotcha with
# `docker run -v ...:/app` masking a baked /app/.venv).
#
# Build
#   docker build -t census-tool-uv .
#
# Interactive shell (repo code on the host, deps from the image)
#   Windows PowerShell:
#     docker run -it --rm -v "${PWD}:/workspace" census-tool-uv
#   cmd.exe:
#     docker run -it --rm -v %CD%:/workspace census-tool-uv
#
# Then: cd /workspace && python -m pytest && python main.py
# (Use .env on the host or pass -e as needed; do not copy secrets into the image.)

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Git is convenient for "play" sessions; add build-essential only if a wheel build fails.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/census-tool-base
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-groups

ENV PATH="/opt/census-tool-base/.venv/bin:${PATH}" \
    VIRTUAL_ENV="/opt/census-tool-base/.venv"

WORKDIR /workspace

CMD ["/bin/bash"]
