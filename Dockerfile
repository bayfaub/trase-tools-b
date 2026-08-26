FROM python:3.13-slim

WORKDIR /app

# git is required to pip-install the source-only trase-os-sdk from the monorepo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt .

# The agent-deploy build offers the repository's OAuth token as the BuildKit
# secret `repo_token`, which is what lets pip clone the private monorepo for
# trase-os-sdk. It is deliberately NOT a --build-arg: build args are recorded in
# image history, so a token passed that way would ship to every registry the
# image is pushed to. See DockerClient.REPO_TOKEN_SECRET_ID in the monorepo.
#
# The secret is mounted at /run/secrets/repo_token for the duration of this RUN
# only, and is read through a git credential helper so it never lands in a layer.
#
# For a manual/local build:
#   printf '%s' "<pat>" > /tmp/repo_token
#   DOCKER_BUILDKIT=1 docker build --secret id=repo_token,src=/tmp/repo_token .
RUN --mount=type=secret,id=repo_token \
    git config --global credential.helper \
      '!f() { echo username=x-access-token; echo "password=$(cat /run/secrets/repo_token)"; }; f' \
    && pip install --no-cache-dir -r requirements.txt \
    && git config --global --unset-all credential.helper || true

COPY . .

# Repo root on PYTHONPATH so `import tools.*` (and register-tool's reported
# module_path) resolve at worker boot exactly as they do locally.
ENV PYTHONPATH=/app

CMD ["python", "worker.py"]
