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
├── Dockerfile            # docker build target for the agent-deploy build VM
├── requirements.txt      # installs trase-os-sdk (source-only, from git)
├── worker.py             # entrypoint: discovers tools/, starts a Temporal worker
└── tools/
    ├── __init__.py
    └── base64_codec_tool.py
```

## Local dev (poll loop, no deploy)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # needs access to the private monorepo
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

Push to the default branch. The agent-deploy webhook builds this repo's
`Dockerfile`, pushes the image to Artifact Registry, Helm-deploys the worker,
and registers it with workflow-service using the enable-step activity names.

## Known gaps (current agent-deploy pipeline)

Same platform limitations as `trase-tools-a`:

1. **Private-dependency install.** `trase-os-sdk` is not on public PyPI; the
   cloud build's plain `docker build` supplies no `GITHUB_TOKEN`, so the SDK
   clone fails unless the pipeline provides repo credentials another way.
2. **Missing runtime env.** agent-deploy injects only `WORKER_NAME` and
   `TEMPORAL_*`, not `TRASE_WORKFLOW_SERVICE_URL` / `TRASE_INTERNAL_TOKEN`.
