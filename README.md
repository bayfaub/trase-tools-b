# trase-tools-b — multi-step ADK agent (experiment branch)

The **ADK** counterpart of `multi-step-agent`. Same shape, different framework,
so the pair isolates one variable:

> Are the flat `sandbox` Steps graph, the silent event timeline, and the
> unreadable logs properties of the third-party agent path — or of LangChain?

If an ADK agent behaves identically, the answer is the path.

## Shape of a run

```
stage 1 (analyst)  --> word_stats                  --> a one-line brief
stage 2 (encoder)  --> base64_codec, sha256_hex    --> a digest record
```

Two `Agent`s driven by `InMemoryRunner`, run in sequence, with **stage 2's
input being stage 1's output**; within a stage the model must chain more than
one tool call. Identical to the LangChain branch in stages, tools, prompts and
log lines — only the framework and the model provider differ.

## Why this file knows about Trase and the LangChain one doesn't

`agent/agent.py` reads `TRASE_VERTEX_BASE_URL` and `TRASE_RUN_ID` directly,
threading both into `Gemini(client_kwargs=...)`. That is unavoidable:
google-genai 2.x exposes **no environment variable** for the base URL, so it
can only be set at client construction. The OpenAI path can be aliased from the
entrypoint shim and leave the agent stock; the Vertex path cannot. This is the
per-SDK cost ADR 0045 exists to remove, and it is itself a finding — "bring
your own stock agent" holds less well for ADK than for LangChain.

`credentials=Credentials(token=TRASE_RUN_ID)` follows the reference ADK agent:
the run credential rides the SDK's key slot for egress correlation, and doubles
as the ADC pacifier so google-genai does not crash into credential discovery in
a sandbox that correctly holds nothing.

## Layout

Bundle at the **repo root** (`trase-agent.yaml`, `requirements.txt`, `agent/`) —
the layout `--repo` onboarding accepts.

## Publish

```bash
trase-os-sdk publish --repo bayfaub/trase-tools-b --ref adk-agent
```

## Branches

| Branch | Framework | Agent | Bundle location |
| --- | --- | --- | --- |
| `main` | LangChain | 1 tool, 1 stage | `trase-tools-b-langchain-agent/` |
| `mainline-test-agent` | LangChain | 1 tool, 1 stage | repo root |
| `multi-step-agent` | LangChain | 3 tools, 2 chained stages | repo root |
| `adk-agent` | ADK | 3 tools, 2 chained stages | repo root |

## What is verified here, and what is not

Verified locally: both agents construct with the right per-stage tools, the
tools behave, `TRASE_VERTEX_BASE_URL` is threaded into the client, JSON logging
is in place, and the runner reaches a real outbound Vertex call (it fails with
`ConnectError` against an unreachable stub).

**Not** verified: an actual Gemini completion. Vertex is not stubbed the way the
OpenAI path was, so the LLM turn and the tool-calling loop have only been
exercised against a real endpoint on the LangChain branch, not here.
