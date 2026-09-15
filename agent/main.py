"""Entrypoint shim: point the stock OpenAI SDK at the governed egress proxy.

The platform injects TRASE_OPENAI_BASE_URL and TRASE_RUN_ID. The OpenAI SDK reads
OPENAI_BASE_URL and OPENAI_API_KEY. Aliasing the two here keeps the agent itself
stock — wrap, don't edit. If the platform injected the SDK-standard names, this
file would not need to exist and `entrypoint` could point straight at the agent.

TRASE_RUN_ID doubles as the run credential the authorizer reads, so it is never
logged — only the base URL, which is what you need to confirm egress wiring.
"""

import logging
import os


log = logging.getLogger(__name__)


def run() -> str:
    base_url = os.environ["TRASE_OPENAI_BASE_URL"]
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_KEY"] = os.environ["TRASE_RUN_ID"]
    log.info("openai egress through %s", base_url)

    from agent.agent import main

    return main()
