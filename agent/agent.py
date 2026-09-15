"""A multi-step ADK agent. The ADK counterpart of the `multi-step-agent` branch.

Same shape as the LangChain version so the two are comparable — two stages in
sequence, each with its own instruction and tool set, stage 2 consuming stage
1's output, and more than one tool call inside a stage:

    stage 1 (analyst)  -> word_stats            -> a short brief
    stage 2 (encoder)  -> base64_codec, sha256  -> a digest record

Only the framework differs. If the Studio still renders one opaque `sandbox`
node and the events/logs surfaces still return nothing for an ADK agent too,
then those are properties of the third-party agent path rather than of
LangChain.

Two lines are platform-shaped, both inside model construction, and both follow
the reference ADK agent in the monorepo (ADR 0032/0033):

- ``credentials=`` carries the run credential in the SDK's own key slot, where
  the authorizer reads it to stamp egress decisions. It also stops google-genai
  from crashing into ADC discovery inside a sandbox that correctly holds no
  credentials. The gateway swaps in the real vendor credential upstream, so the
  value never reaches Google.
- ``http_options=`` is the only way to set a base URL: google-genai 2.x has no
  environment variable for it, so the platform-injected TRASE_VERTEX_BASE_URL
  has to be threaded through code. That is the per-SDK cost ADR 0045 exists to
  remove, and it is why this file — unlike the LangChain one — cannot be
  entirely ignorant of Trase.
"""

import asyncio
import base64
import binascii
import hashlib
import logging
import os

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.oauth2.credentials import Credentials


log = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
SUBJECT = "Trase OS third party agent onboarding"


def word_stats(text: str) -> str:
    """Count the words and characters in a piece of text.

    Args:
        text: The text to measure.
    """
    words = len(text.split())
    log.info("tool word_stats invoked: words=%d chars=%d", words, len(text))
    return f"{words} words, {len(text)} characters"


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


def sha256_hex(text: str) -> str:
    """Return the hex SHA-256 digest of a string.

    Args:
        text: The text to hash.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    log.info("tool sha256_hex invoked: input_len=%d digest_prefix=%s", len(text), digest[:12])
    return digest


def _model() -> Gemini:
    """Gemini over Vertex, pointed at the governed egress proxy."""
    return Gemini(
        model=MODEL,
        client_kwargs={
            "vertexai": True,
            "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "trase-dev"),
            "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            "credentials": Credentials(token=os.environ.get("TRASE_RUN_ID", "placeholder")),
            "http_options": types.HttpOptions(base_url=os.environ["TRASE_VERTEX_BASE_URL"]),
        },
    )


def analyst() -> Agent:
    """Stage 1: measure the subject and write a one-line brief."""
    return Agent(
        name="analyst",
        model=_model(),
        instruction=(
            "You are a text analyst. Call word_stats on the text you are given, "
            "then reply with one line: the text, followed by its statistics. "
            "Do not count words yourself."
        ),
        tools=[word_stats],
    )


def encoder() -> Agent:
    """Stage 2: encode the brief, then hash the encoding."""
    return Agent(
        name="encoder",
        model=_model(),
        instruction=(
            "You produce digest records. First call base64_codec to encode the "
            "text you are given. Then call sha256_hex on the base64 string you "
            "got back. Reply with both values, labelled. Never compute either "
            "value yourself — always use the tools."
        ),
        tools=[base64_codec, sha256_hex],
    )


async def _run_stage(agent: Agent, prompt: str, label: str) -> str:
    """Drive one agent to completion, logging its tool calls and its text."""
    runner = InMemoryRunner(agent=agent, app_name=label)
    session = await runner.session_service.create_session(app_name=label, user_id="probe")

    chunks: list[str] = []
    called: list[str] = []
    async for event in runner.run_async(
        user_id="probe",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        parts = event.content.parts if event.content and event.content.parts else []
        for part in parts:
            call = getattr(part, "function_call", None)
            if call is not None and getattr(call, "name", None):
                called.append(call.name)
                log.info("%s model called tool: %s", label, call.name)
            text = getattr(part, "text", None)
            if text:
                chunks.append(text)
        usage = getattr(event, "usage_metadata", None)
        if usage:
            log.info(
                "token usage: prompt=%s response=%s",
                getattr(usage, "prompt_token_count", "?"),
                getattr(usage, "candidates_token_count", "?"),
            )

    log.info("%s tools called: %s", label, ", ".join(called) if called else "none")
    text = "".join(chunks)
    assert text.strip(), f"{label} produced no text"
    return text


async def _amain() -> str:
    log.info("stage 1/2 (analyst) starting; model=%s subject=%r", MODEL, SUBJECT)
    brief = await _run_stage(analyst(), SUBJECT, "stage 1/2")
    log.info("stage 1/2 output: %s", brief.strip())

    log.info("stage 2/2 (encoder) starting; input is stage 1 output")
    digest = await _run_stage(encoder(), brief, "stage 2/2")
    log.info("stage 2/2 output: %s", digest.strip())

    log.info("run complete: 2 stages")
    return digest


def main() -> str:
    return asyncio.run(_amain())
