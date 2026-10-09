# CreatorForge on a normal laptop (Docker, Windows/WSL2)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System bits Pillow sometimes wants; kept minimal.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        libjpeg62-turbo libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY forge/ ./forge/
COPY scripts/ ./scripts/
COPY examples/ ./examples/
COPY docs/ ./docs/
COPY assets/ ./assets/

RUN pip install --upgrade pip -q \
    && pip install -q "."

# Data lives OUTSIDE the image (mounted volumes): catalog DB, vault,
# identity packs, chat queue, word bank. Nothing personal bakes in.
# These match the app's default paths (forge-data/, identity-packs/).
VOLUME ["/app/forge-data", "/app/identity-packs"]

EXPOSE 8765

# Default: serve the dashboard. Override for CLI, e.g.
#   docker compose run --rm forge chat lexicon-list
CMD ["forge", "dashboard", "--host", "0.0.0.0", "--port", "8765"]
