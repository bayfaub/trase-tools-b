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
└── tools/
    ├── __init__.py
    └── base64_codec_tool.py
```

A repository `Dockerfile` is rejected by agent-build-service (`DOCKERFILE_NOT_ALLOWED`).

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

Push to the default branch. agent-deploy dispatches to agent-build-service,
which requires repo-root `build.sh` + `run.sh` (with a shebang) and rejects a
repository Dockerfile. The platform generates the wrapper image, pushes it,
Helm-deploys the worker, and registers it with workflow-service using the
enable-step activity names.

## Known gaps

1. **Private SDK install.** `requirements.txt` clones `trase-os-sdk` from the
   private monorepo. The legacy `agent-deploy-worker` offered that token as the
   BuildKit secret `repo_token`. agent-build-service does not, so `build.sh`'s
   `pip install` may still fail on the new builder until the SDK is reachable
   without a GitHub credential (hash-pinned public deps, as in
   `TraseSystems/agent-build-e2e-fixture`).
2. **Missing runtime env (may be stale).** Older notes said agent-deploy did
   not inject `TRASE_WORKFLOW_SERVICE_URL` / `TRASE_INTERNAL_TOKEN`. Confirm
   against the current `WorkloadValuesBuilder` before treating a boot
   `KeyError` as expected.
