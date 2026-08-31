#!/bin/bash
# Platform-generated wrapper Dockerfile invokes this as the image's build step
# (ADR 0034: build.sh-only, no repository Dockerfile).
set -euo pipefail

pip install --no-cache-dir -r requirements.txt
