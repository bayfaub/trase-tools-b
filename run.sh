#!/bin/bash
# The generated wrapper's runtime CMD execs this directly.
# PYTHONPATH=/app so `import tools` resolves the same as the old Dockerfile ENV.
set -euo pipefail

export PYTHONPATH=/app
exec python worker.py
