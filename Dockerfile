FROM python:3.13-slim

WORKDIR /app

# git is required to pip-install the source-only trase-os-sdk from the monorepo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt .

# GITHUB_TOKEN lets pip clone the private monorepo for trase-os-sdk.
#
# NOTE: the current agent-deploy build runs a plain `docker build` without
# passing build-args, so this token is NOT supplied in the cloud pipeline —
# a KNOWN GAP for private-dependency installs (see README "Known gaps").
# For a manual/local build:  docker build --build-arg GITHUB_TOKEN=<pat> .
ARG GITHUB_TOKEN=""
RUN if [ -n "$GITHUB_TOKEN" ]; then \
        git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"; \
    fi \
    && pip install --no-cache-dir -r requirements.txt \
    && git config --global --unset-all url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf || true

COPY . .

# Repo root on PYTHONPATH so `import tools.*` (and register-tool's reported
# module_path) resolve at worker boot exactly as they do locally.
ENV PYTHONPATH=/app

CMD ["python", "worker.py"]
