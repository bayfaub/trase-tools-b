# trase-tools-b — multi-step agent (experiment branch)

A deliberately **multi-step** LangChain agent, published as an agent bundle from
the root of this branch. It exists to answer one question:

> When the agent has real internal structure, does the platform surface any more
> of it — a Steps graph with more than one node, events, retrievable logs?

If the answer is no, then the flat `sandbox` topology and the empty
events/logs surfaces are properties of the third-party agent path, not of how
thin the agent under test happened to be.

## Shape of a run

```
stage 1 (analyst)  --> word_stats                  --> a one-line brief
stage 2 (encoder)  --> base64_codec, sha256_hex    --> a digest record
```

Two separate `create_agent` invocations, each with its own system prompt and
tool set, run in sequence; **stage 2's input is stage 1's output**. Within a
stage the model must chain more than one tool call. One run therefore performs
two LLM stages and three tool calls, versus the single-tool single-stage agent
on `mainline-test-agent`.

Every tool logs its own invocation and every stage boundary is logged, so the
run's shape is recoverable from the log stream alone — 14 log lines for a
normal run.

## Layout

The bundle sits at the **repo root** (`trase-agent.yaml`, `requirements.txt`,
`agent/`), not in a subdirectory. That is the layout the platform accepts for
`--repo` onboarding; a nested bundle is rejected with
`expected 'trase-agent.yaml' at the bundle root`.

## Publish

```bash
trase-os-sdk publish --repo bayfaub/trase-tools-b --ref multi-step-agent
```

## Compared with the other branches

| Branch | Agent | Bundle location |
| --- | --- | --- |
| `main` | single tool, one stage | `trase-tools-b-langchain-agent/` |
| `mainline-test-agent` | single tool, one stage | repo root |
| `multi-step-agent` | 3 tools, two chained stages | repo root |

Logging is identical across all three (JSON, so Promtail can extract
`timestamp`/`level`/`logger`/`message`), so any difference observed is about
agent structure, not about the log format.
