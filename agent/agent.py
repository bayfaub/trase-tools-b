"""An ordinary LangChain agent. Nothing here knows it runs on Trase.

Reads OPENAI_API_KEY / OPENAI_BASE_URL from the environment, which is what the
OpenAI SDK does by default — no base_url or api_key threaded through code.

The tool below mirrors this repo's `Base64Codec` worker tool, so the agent has
something deterministic to call and the sample exercises a real tool-call turn
rather than a bare completion.
"""

import base64
import binascii

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


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
    if op == "encode":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    try:
        return base64.b64decode(text.encode("ascii"), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid base64 input: {exc}") from exc


def build():
    return create_agent(
        ChatOpenAI(model="gpt-4o-mini"),
        tools=[base64_codec],
        system_prompt=(
            "You are a concise assistant. Use the base64_codec tool for any "
            "encoding or decoding request instead of doing it in your head."
        ),
    )


def main() -> str:
    result = build().invoke(
        {"messages": [{"role": "user", "content": "Base64-encode the word 'trase'."}]}
    )
    return result["messages"][-1].content
