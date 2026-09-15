"""Entrypoint shim: JSON logging, then point the stock OpenAI SDK at the proxy.

Two platform-shaped concerns live here so that agent/agent.py stays a stock
LangChain agent with no Trase imports. Wrap, don't edit.

1. Logging format. The per-run log API reads Loki, and Promtail extracts
   `timestamp`, `level`, `logger` and `message` by parsing each line as JSON
   (infrastructure/shared/promtail-pipeline-stages.yaml, Stage 1). The base
   image's launcher configures plain `%(message)s`, so an agent that logs
   normally is reachable but degraded: no `level` label — which means a
   severity-filtered query drops the line from the stream selector entirely —
   no `logger`, and no parseable `timestamp`, so Stage 1b falls back to
   Promtail's scrape time. That fallback is the dangerous one: the per-run
   query is bounded to the run window padded by only 5s, so batched scrape
   times can land a line outside its own run's window and lose it.

   Emitting JSON fixes all three. Identity is NOT emitted here: service_name
   and workflow_execution_id are stamped from outside, off pod labels, by
   Promtail Stage 4b and the observability module's extraRelabelConfigs —
   the platform deliberately does not trust sandboxed code to self-report it.

2. Egress. The platform injects TRASE_OPENAI_BASE_URL and TRASE_RUN_ID; the
   OpenAI SDK reads OPENAI_BASE_URL and OPENAI_API_KEY. TRASE_RUN_ID doubles as
   the run credential, so it is never logged — only the base URL.
"""

import json
import logging
import os
from datetime import datetime, timezone


log = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    """Render a record as the flat JSON object the Promtail pipeline parses."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return json.dumps(
            {
                "timestamp": timestamp,
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
        )


def configure_json_logging() -> None:
    """Replace the launcher's plain-text root handler with a JSON one.

    ``force=True`` is required: the base image's launch.py already called
    basicConfig at import, and without it a second call is a silent no-op.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def run() -> str:
    configure_json_logging()

    base_url = os.environ["TRASE_OPENAI_BASE_URL"]
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_KEY"] = os.environ["TRASE_RUN_ID"]
    log.info("openai egress through %s", base_url)

    from agent.agent import main

    return main()
