"""An ordinary LangChain agent. Nothing here knows it runs on Trase.

Reads OPENAI_API_KEY / OPENAI_BASE_URL from the environment, which is what the
OpenAI SDK does by default — no base_url or api_key threaded through code.

The tool below mirrors this repo's `Base64Codec` worker tool, so the agent has
something deterministic to call and the sample exercises a real tool-call turn
rather than a bare completion.

Logging matches the reference agents in the monorepo's
core/workflows/test_examples/third_party_agents/: a sandboxed run leaves no
trace except what it logs, so prompt, tool calls, completion and token usage
are all emitted. The asserts turn a silent empty completion — which the
launcher would otherwise print as a blank line — into a loud failure.
"""

import base64
import binascii
import logging

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


log = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
PROMPT = "Base64-encode the word 'trase'."


@tool
def base64_codec(text: str, mode: str = "encode") -> str:
    """Base64-encode or -decode a UTF-8 string.

    Args:
        text: The input text to encode or decode.
        mode: Either 'encode' (text -> base64) or 'decode' (base64 -> text).
    """
    op = mode.strip().lower()
    if op not in ("encode", "decode"):
        raise ValueError(f"mode must be 'encode' or 'decode'; got {mode!r}")
    log.info("tool base64_codec invoked: mode=%s input_len=%d", op, len(text))
    if op == "encode":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    try:
        return base64.b64decode(text.encode("ascii"), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid base64 input: {exc}") from exc


def build():
    return create_agent(
        ChatOpenAI(model=MODEL),
        tools=[base64_codec],
        system_prompt=(
            "You are a concise assistant. Use the base64_codec tool for any "
            "encoding or decoding request instead of doing it in your head."
        ),
    )


def main() -> str:
    log.info("llm input (%s): %s", MODEL, PROMPT)
    result = build().invoke({"messages": [{"role": "user", "content": PROMPT}]})

    messages = result["messages"]
    called = [c["name"] for m in messages for c in getattr(m, "tool_calls", None) or []]
    log.info("tool calls made: %s", ", ".join(called) if called else "none")

    reply = messages[-1]
    usage = getattr(reply, "usage_metadata", None)
    if usage:
        log.info(
            "token usage: input=%s output=%s",
            usage.get("input_tokens", "?"),
            usage.get("output_tokens", "?"),
        )

    content = reply.content
    assert isinstance(content, str), f"final message content is not a string: {reply!r}"
    assert content.strip(), f"agent produced no text: {result!r}"
    log.info("llm output: %s", content)
    return content
