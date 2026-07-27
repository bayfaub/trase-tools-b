"""Cloud tool-worker entrypoint.

Discovers every :class:`~trase_os_sdk.tools.base_tool.BaseTool` subclass under
the local ``tools/`` package, wraps each as a Temporal activity, and starts an
``ActivityWorker`` that polls the task queue injected by the Trase agent-deploy
Helm chart.

Runtime environment variables:

    TEMPORAL_TASK_QUEUE         required — the queue this worker polls
    TEMPORAL_HOST               Temporal frontend host:port (default localhost:7233)
    TEMPORAL_NAMESPACE          Temporal namespace (default "default")
    TRASE_WORKFLOW_SERVICE_URL  workflow-service base URL (payload hydration) [*]
    TRASE_INTERNAL_TOKEN        static bearer accepted by workflow-service     [*]

The TEMPORAL_* vars are injected by the agent-deploy Helm chart. The two marked
[*] are NOT injected by agent-deploy today (see README "Known gaps") — provide
them as cluster secrets / chart values, or the worker cannot hydrate payloads.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import pkgutil

from trase_os_sdk.activities.activity_worker import ActivityWorker
from trase_os_sdk.activities.http_payload_store import HttpActivityPayloadStore
from trase_os_sdk.clients.workflow_service.client import Client
from trase_os_sdk.clients.workflow_service.factory import WorkflowClientOptions, get_client
from trase_os_sdk.tools.base_tool import BaseTool
from trase_os_sdk.tools.tool_activity import LocalToolActivity

import tools


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("tool_worker")


def _all_named_subclasses(base: type[BaseTool]) -> list[type[BaseTool]]:
    """Return every concrete BaseTool subclass that declares a ``name``."""
    found: dict[str, type[BaseTool]] = {}
    stack = list(base.__subclasses__())
    while stack:
        cls = stack.pop()
        name = getattr(cls, "name", None)
        if isinstance(name, str) and name:
            found[name] = cls
        stack.extend(cls.__subclasses__())
    return sorted(found.values(), key=lambda c: c.name)


def _discover_tools() -> list[type[BaseTool]]:
    """Import every module under ``tools/`` then collect BaseTool subclasses."""
    for module_info in pkgutil.iter_modules(tools.__path__, prefix="tools."):
        importlib.import_module(module_info.name)
    return _all_named_subclasses(BaseTool)


def _build_client() -> Client:
    """Build an authenticated workflow-service client from the environment."""
    base_url = os.environ["TRASE_WORKFLOW_SERVICE_URL"]
    token = os.environ["TRASE_INTERNAL_TOKEN"]
    return get_client(token=token, options=WorkflowClientOptions(base_url=base_url))


async def _amain() -> None:
    tool_classes = _discover_tools()
    if not tool_classes:
        raise SystemExit("No BaseTool subclasses found under tools/ — nothing to serve.")

    client = _build_client()
    payload_store = HttpActivityPayloadStore(client)
    activities = [
        LocalToolActivity(payload_store, cls(), client=client) for cls in tool_classes
    ]

    logger.info(
        "Starting tool worker queue=%s tools=%s",
        os.getenv("TEMPORAL_TASK_QUEUE", "<unset>"),
        [cls.name for cls in tool_classes],
    )
    await ActivityWorker.start(activities=activities)


if __name__ == "__main__":
    asyncio.run(_amain())
