r"""Base64Codec: base64-encode or -decode a string.

Pure local computation — no network, no secrets. A deterministic smoke-test
tool for the Trase OS tools deployment pipeline.

Serve locally with:

    trase-os-sdk run-tool tools/base64_codec_tool.py
"""

from __future__ import annotations

import base64
import binascii
from typing import ClassVar

from pydantic import BaseModel, Field
from trase_os_sdk.tools import BaseTool


_MODES = ("encode", "decode")


class Base64Inputs(BaseModel):
    """Parameters for a single base64 encode/decode call."""

    text: str = Field(description="The input text to encode or decode.")
    mode: str = Field(
        default="encode",
        description="Operation: 'encode' (text -> base64) or 'decode' (base64 -> text).",
    )


class Base64Result(BaseModel):
    """Structured codec result."""

    result: str = Field(description="The encoded or decoded output string.")
    mode: str = Field(description="The operation that was performed.")
    summary: str = Field(description="Human-readable summary of the operation.")


class Base64Codec(BaseTool):
    """Base64-encode or -decode a UTF-8 string."""

    name: ClassVar[str] = "Base64Codec"
    description: ClassVar[str] = (
        "Base64-encode or -decode a UTF-8 string. Set mode to 'encode' or "
        "'decode'. Returns a Base64Result JSON object."
    )
    pydantic_inputs: ClassVar[type[BaseModel]] = Base64Inputs
    output_type: ClassVar[str] = "object"
    output_schema: ClassVar[dict] = Base64Result.model_json_schema()

    def forward(self, text: str, mode: str = "encode") -> Base64Result:
        """Encode or decode ``text`` per ``mode``."""
        op = mode.strip().lower()
        if op not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}; got {mode!r}")
        if op == "encode":
            result = base64.b64encode(text.encode("utf-8")).decode("ascii")
        else:
            try:
                result = base64.b64decode(text.encode("ascii"), validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
                raise ValueError(f"invalid base64 input: {exc}") from exc
        return Base64Result(
            result=result,
            mode=op,
            summary=f"{op}d {len(text)} character(s) -> {len(result)} character(s)",
        )
