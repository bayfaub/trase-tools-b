"""A multi-step LangChain agent. Nothing here knows it runs on Trase.

Two distinct agent stages run in sequence, each with its own system prompt and
its own tool set, and stage 2 consumes stage 1's output. Within a stage the
model must also chain several tool calls. So a single run produces:

    stage 1 (analyst)  -> word_stats            -> a short brief
    stage 2 (encoder)  -> base64_codec, sha256  -> a digest record

That is deliberately more structure than the single-tool agent on
`mainline-test-agent`: if the Studio's Steps graph still renders one opaque
`sandbox` node, and the per-run events/logs surfaces still return nothing, then
what we are looking at is a property of the platform's third-party agent path
rather than of how thin the agent was.

Every tool logs its own invocation, and each stage boundary is logged, so the
run's shape is recoverable from the log stream alone.
"""

import base64
import binascii
import hashlib
import logging

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


log = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
SUBJECT = "Trase OS third party agent onboarding"


@tool
def word_stats(text: str) -> str:
    """Count the words and characters in a piece of text.

    Args:
        text: The text to measure.
    """
    words = len(text.split())
    log.info("tool word_stats invoked: words=%d chars=%d", words, len(text))
    return f"{words} words, {len(text)} characters"


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


@tool
def sha256_hex(text: str) -> str:
    """Return the hex SHA-256 digest of a string.

    Args:
        text: The text to hash.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    log.info("tool sha256_hex invoked: input_len=%d digest_prefix=%s", len(text), digest[:12])
    return digest


def analyst():
    """Stage 1: measure the subject and write a one-line brief."""
    return create_agent(
        ChatOpenAI(model=MODEL),
        tools=[word_stats],
        system_prompt=(
            "You are a text analyst. Call word_stats on the text you are given, "
            "then reply with one line: the text, followed by its statistics. "
            "Do not count words yourself."
        ),
    )


def encoder():
    """Stage 2: encode the brief, then hash the encoding."""
    return create_agent(
        ChatOpenAI(model=MODEL),
        tools=[base64_codec, sha256_hex],
        system_prompt=(
            "You produce digest records. First call base64_codec to encode the "
            "text you are given. Then call sha256_hex on the base64 string you "
            "got back. Reply with both values, labelled. Never compute either "
            "value yourself — always use the tools."
        ),
    )


def _last_text(result) -> str:
    """The final assistant text of a stage, validated as non-empty."""
    reply = result["messages"][-1]
    usage = getattr(reply, "usage_metadata", None)
    if usage:
        log.info(
            "token usage: input=%s output=%s",
            usage.get("input_tokens", "?"),
            usage.get("output_tokens", "?"),
        )
    content = reply.content
    assert isinstance(content, str), f"final message content is not a string: {reply!r}"
    assert content.strip(), f"stage produced no text: {result!r}"
    return content


def _tools_called(result) -> list[str]:
    """Names of every tool the model called during a stage, in order."""
    return [c["name"] for m in result["messages"] for c in getattr(m, "tool_calls", None) or []]


def main() -> str:
    log.info("stage 1/2 (analyst) starting; model=%s subject=%r", MODEL, SUBJECT)
    brief_result = analyst().invoke({"messages": [{"role": "user", "content": SUBJECT}]})
    log.info("stage 1/2 tools called: %s", ", ".join(_tools_called(brief_result)) or "none")
    brief = _last_text(brief_result)
    log.info("stage 1/2 output: %s", brief)

    log.info("stage 2/2 (encoder) starting; input is stage 1 output")
    digest_result = encoder().invoke({"messages": [{"role": "user", "content": brief}]})
    log.info("stage 2/2 tools called: %s", ", ".join(_tools_called(digest_result)) or "none")
    digest = _last_text(digest_result)
    log.info("stage 2/2 output: %s", digest)

    log.info("run complete: 2 stages, %d total tool calls",
             len(_tools_called(brief_result)) + len(_tools_called(digest_result)))
    return digest
