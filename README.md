# trase-tools-b

Second test tool-worker repo for exercising the Trase OS tools deployment
pipeline. Its derived worker name differs from `trase-tools-a`, which is what
makes the T7b duplicate-registration test (409 "already registered to a
different worker") fire.

Derived worker name (via `ContainerNames.derive`): **`bayfaub-trase-tools-b`**
Task queue: **`bayfaub-trase-tools-b-queue`**

## Tools served

| Tool `name`   | File                          | What it does                       |
| ------------- | ----------------------------- | ---------------------------------- |
| `Base64Codec` | `tools/base64_codec_tool.py`  | Base64-encode or -decode a string  |

**Enable-webhook activity list** (paste into the "tool/activity names" modal):

```
Base64Codec
```

This must match the tool's `name` exactly (case-sensitive).

## Layout

```
.
├── build.sh              # image build step (ADR 0034; the platform authors the Dockerfile)
├── run.sh                # container entrypoint
├── requirements.txt      # installs trase-os-sdk (source-only, from git)
├── worker.py             # discovers tools/, starts a Temporal worker
├── tools/
│   ├── __init__.py
│   └── base64_codec_tool.py
└── trase-tools-b-langchain-agent/   # agent bundle — a separate artifact (see below)
    ├── trase-agent.yaml
    ├── requirements.txt
    └── agent/
        ├── __init__.py
        ├── agent.py                 # stock LangChain; knows nothing about Trase
        └── main.py                  # entrypoint shim: env aliasing for governed egress
```

A repository `Dockerfile` is rejected by agent-build-service (`DOCKERFILE_NOT_ALLOWED`).

## Sample LangChain agent (agent bundle)

`trase-tools-b-langchain-agent/` is a **sample agent bundle**, not a tool. It
rides a different lifecycle from everything else in this repo: the tool worker
above is built from root `build.sh`/`run.sh` and deployed by agent-deploy; a
bundle is zipped and pushed to the **agent registry** (`trase-os-sdk build` /
`release`), which builds it from the bundle's own `requirements.txt` and
launches its `entrypoint`. The two do not interact — the bundle is here as a
worked example, and adding it changes nothing about the worker's deploy.

The manifest is the whole contract:

```yaml
name: trase-tools-b-langchain-agent   # [a-z0-9][a-z0-9-]{0,63}
framework: langchain                  # metadata only — the build is framework-agnostic
entrypoint: agent.main:run            # <module>:<callable>, invocable with NO arguments
```

`framework` is never a build gate, and `entrypoint` must name a *callable*, not
an already-constructed app instance — the launcher calls whatever it names at
container start, so an instance raises `TypeError` instead of serving.

### The egress shim is the point

The platform injects `TRASE_OPENAI_BASE_URL` and `TRASE_RUN_ID`; the OpenAI SDK
reads `OPENAI_BASE_URL` and `OPENAI_API_KEY`. `agent/main.py` aliases one pair
onto the other and nothing else, so `agent/agent.py` stays a stock LangChain
agent with no Trase imports and no base_url/api_key threaded through it. Wrap,
don't edit. If the platform ever injected the SDK-standard names, `main.py`
would disappear and `entrypoint` could point straight at the agent.

The agent calls one tool (`base64_codec`, mirroring the worker's `Base64Codec`)
so the sample exercises a real tool-call turn rather than a bare completion.

### Publish it

```bash
trase-os-sdk login
trase-os-sdk publish ./trase-tools-b-langchain-agent   # build, then release (irreversible)
```

Or the two-step form when you want to inspect the image before burning a
version number:

```bash
trase-os-sdk build ./trase-tools-b-langchain-agent
trase-os-sdk release trase-tools-b-langchain-agent
```

## Local dev (poll loop, no deploy)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # needs read access to TraseSystems/trase-os-sdk
trase-os-sdk login
trase-os-sdk run-tool tools/base64_codec_tool.py
```

## Register the tool

Repo must already be connected+enabled:

```bash
trase-os-sdk register-tool tools/base64_codec_tool.py --repo bayfaub/trase-tools-b
```

### T7b (duplicate registration → 409)

Register a tool that is already registered against `trase-tools-a` but pass
`--repo bayfaub/trase-tools-b`. Because the derived worker name differs, the
server rejects it with `409 "already registered to a different worker"`:

```bash
# already registered to bayfaub-trase-tools-a earlier:
trase-os-sdk register-tool ../trase-tools-a/tools/word_counter_tool.py --repo bayfaub/trase-tools-b
```

## Deploy

Push to the default branch. agent-deploy dispatches to agent-build-service,
which requires repo-root `build.sh` + `run.sh` (with a shebang) and rejects a
repository Dockerfile. The platform generates the wrapper image, pushes it,
Helm-deploys the worker, and registers it with workflow-service using the
enable-step activity names.

## Known gaps

1. **Private SDK install.** `requirements.txt` installs `trase-os-sdk` from
   `TraseSystems/trase-os-sdk` over `git+https`. agent-build-service mints a
   GitHub App installation token per build and hands it to `build.sh` as a
   BuildKit secret, so no credential lives in this repo. It still needs the SDK
   App configured on the build VM and a tool base image carrying `git`; until
   both are in place the `pip install` fails inside the build.

   The requirement must name the SDK repository, not the monorepo — the App is
   installed on `TraseSystems/trase-os-sdk` alone, so any other repository is
   refused with `Repository not found` even with a valid token.
2. **Missing runtime env (may be stale).** Older notes said agent-deploy did
   not inject `TRASE_WORKFLOW_SERVICE_URL` / `TRASE_INTERNAL_TOKEN`. Confirm
   against the current `WorkloadValuesBuilder` before treating a boot
   `KeyError` as expected.
