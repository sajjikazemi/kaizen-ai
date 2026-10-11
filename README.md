# KaizenAI

[![CI](https://github.com/sajjikazemi/kaizen-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/sajjikazemi/kaizen-ai/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kaizen_ai)](https://pypi.org/project/kaizen-ai/)
[![License: MIT](https://img.shields.io/pypi/l/kaizen_ai)](LICENSE)

**Kaizen (改善)**: continuous, incremental improvement. KaizenAI is an
autonomous agent that finds failing tests, proposes the smallest fix, and
opens a gated pull request for human review — it never commits directly.
Built so it can be pointed at *any* project without changes to the
framework itself.

## How it works

1. **Runner agent** connects to a target project — via shell commands
   and/or [MCP](https://modelcontextprotocol.io) (the open protocol both
   agents use to access a project's tools) — and executes that project's
   **eval suite**: a small set of representative tasks with clear pass/fail
   criteria.
2. Every result (pass or fail) is written to a structured **trace store**
   (JSONL), including which prompt/tool-schema version produced it.
3. **Fixer agent** reads failing traces and proposes the smallest possible
   patch — preferring prompts/config/tool descriptions over application
   code when that's the root cause.
4. Every patch is scoped into a **risk tier** (safe text/config vs.
   application code vs. never-touch) and opened as a **pull request** — never
   committed directly. A human always reviews and merges.

```
Runner ──runs evals──▶ Target project (via MCP / shell)
   │
   ▼
Trace store (structured failures)
   │
   ▼
Fixer ──proposes patch──▶ git branch ──▶ PR ──▶ Human review ──▶ merge
```

### Eval case types

An eval case is exactly one of these three, in increasing order of cost
and decreasing order of determinism:

| Type | What it does | When to use |
|---|---|---|
| `command` | Runs a shell command (`dotnet test`, `pytest`), parses output via the configured adapter | Default choice - deterministic, no LLM, fast |
| `mcp_tool_call` | One scripted call to a tool on the target's MCP server (`tool` + `arguments`), checked against the raw result (`isError`, content) | Testing an MCP server directly - isolates one tool's behavior without an agent's reasoning in the way |
| `task_prompt` | A natural-language task handed to an LLM agent connected over MCP | Behavior that isn't a simple pass/fail call - slower, less reproducible, needs a model |

```yaml
# command
- id: tests-pass
  command: ["pytest"]
  expect_exit_code: 0

# mcp_tool_call
- id: search-tool-returns-results
  mcp_tool_call:
    tool: search
    arguments: {query: "test"}
  expect_output_contains: ["results"]

# task_prompt
- id: can-provision-a-device
  task_prompt: "Provision a new device via the API and confirm it appears in the device list."
```

## Quickstart (5 minutes, no target project of your own needed)

This repo ships `examples/sample_python_project/` — a tiny, self-contained
project with one deliberately broken function — so you can watch the
Runner catch a real failure with zero setup:

```bash
git clone https://github.com/sajjikazemi/kaizen-ai.git
cd kaizen-ai
poetry install

poetry run kaizen run --config examples/sample_python_project/kaizen.yaml
```

That runs `pytest` against the example project and reports one failing
case — `subtract()` has a bug (see `calculator.py`). No API key needed for
this step.

To see the **Fixer** actually propose a patch, you'll need an LLM key
(`cp .env.example .env`, fill in `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, or
log into the GitHub Copilot CLI — see below) and then:

```bash
poetry run kaizen fix --config examples/sample_python_project/kaizen.yaml
```

**Heads up:** since the example lives inside this repo rather than a
separate one, `kaizen fix` checks out a real `kaizen/fix/...` branch *in
your `kaizen-ai` clone* (that's how it behaves against any target repo).
Skip `--open-pr` to just inspect the diff, or try this against a scratch
clone if you'd rather not touch your working branch.

## Adding a new target project

Fast path - `kaizen init [path]` auto-detects the adapter (pyproject.toml
→ `pytest`, `*.csproj`/`*.sln` → `dotnet`) and the git default branch,
then scaffolds a `kaizen.yaml` + one catch-all eval case that runs the
whole test suite:

```bash
kaizen init path/to/target/project
kaizen run --config path/to/target/project/kaizen.yaml
```

That gets you a working pass/fail signal immediately - it's a starting
point, not a finished eval suite (see step 2 below). `--adapter` overrides
detection; `--force` overwrites an existing `kaizen.yaml`.

Manual setup, or to go beyond the single catch-all case:

1. Add a `kaizen.yaml` to the target repo and pick an adapter —
   `dotnet` (see `examples/sample_dotnet_project/kaizen.yaml`) or
   `pytest` (see `examples/sample_python_project/kaizen.yaml`). Add a new
   language by implementing `ProjectAdapter` (`src/kaizen/adapters/base.py`)
   and registering it in `src/kaizen/adapters/__init__.py`.
2. Add an `evals/` directory with one `*.eval.yaml` file per case, tagged
   by feature area (see either example's `evals/`) - this is what the
   statistical treatment/control gate uses to decide what else to re-test
   alongside a failing case, so it's worth curating beyond `kaizen init`'s
   single catch-all.
3. Run:
   ```bash
   kaizen baseline --config path/to/kaizen.yaml      # cache ground-truth (run on a cadence, e.g. nightly)
   kaizen run --config path/to/kaizen.yaml           # find today's failures
   kaizen fix --config path/to/kaizen.yaml --open-pr # propose, evaluate, and PR each fix
   ```

## Statistically-gated regression safety

Fixing failures and verifying nothing else broke are two different
problems — at 200+ eval cases you can't afford to re-run everything on
every candidate, nor can you trust a 5-question spot check. Kaizen uses a
paired **treatment/control** evaluation (`kaizen evaluate`), the same
methodology used for online A/B testing and NLP model regression testing:

- **Treatment split** = the failing case(s) + any case sharing a tag
  (feature area) with them.
- **Control split** = a stratified random sample of everything else,
  rotated across cycles so full coverage accumulates over time instead of
  being paid for on every run.
- Baseline vs. candidate results on both splits are compared with
  **McNemar's test** (the statistically correct test for paired binary
  before/after outcomes), not a plain percentage diff.
- **Decision rule:** significant gain on treatment + flat control → `fix`
  (open PR). Gain on treatment + significant loss on control → `trade`
  (PR opened but flagged for explicit human judgment). No significant
  treatment gain → `rejected` (no PR; Fixer iterates again).

See `docs/README.md` for the supporting papers (McNemar 1947; Dietterich
1998; Dror et al. 2018; Ribeiro et al. 2020; Sculley et al. 2015; Kohavi
et al. 2009; Rothermel & Harrold 1996; Yoo & Harman 2012; Cochran 1977).

## Risk tiers

| Tier | Scope | Review |
|---|---|---|
| 1 — safe | prompts, tool descriptions, eval/config files, docs | lightweight |
| 2 — code | application source code | always required |
| 3 — locked | secrets, infra, CI/CD config | Fixer may never modify |

## Agent runtime: two swappable backends

Runner and Fixer each delegate to a **backend**, picked per project via
`model.backend` in `kaizen.yaml` — nothing else in the codebase needs to
change to switch:

| Backend | How it works | When to use |
|---|---|---|
| `copilot_cli` (default) | Shells out to the already-authenticated **GitHub Copilot CLI** (`copilot -p ...`, non-interactive mode) — each call is a fresh/isolated session (or a resumed one via `--session-id` for follow-ups), using the operator's existing Copilot subscription | No separate LLM API key/deployment available yet |
| `langgraph` | Direct provider API calls via **LangGraph** (`langchain.agents.create_agent`), model picked with LangChain's `"provider:model"` string (`model.runner_model`/`model.fixer_model`) | Once a direct Anthropic/OpenAI/Bedrock/local-model deployment exists |

Both live behind a thin dispatcher (`runner/mcp_task.py`, `fixer/dispatch.py`)
so `FixerAgent`/`RunnerAgent`, tiering, evaluation, and the PR gate are
identical either way.

- **Runner** connects to the target's MCP server (via `langchain-mcp-adapters`
  for the `langgraph` backend, or Copilot CLI's own `--additional-mcp-config`
  for `copilot_cli`) and drives `task_prompt` eval cases.
- **Fixer** edits files via `Read`/`Write`/`Edit`/`Bash`. Tier-3 enforcement
  differs slightly by backend:
  - `langgraph`: hard-blocked in the tool itself (`fixer/tools.py`), plus
    Tier-2 writes pause for approval via `HumanInTheLoopMiddleware`.
  - `copilot_cli`: the CLI has no per-tool-call hook, so Tier-3 is enforced
    **post-hoc** — after the session, any Tier-3 file in the diff is
    hard-reverted (`fixer/git_tier_guard.py`) before anything reaches the PR.
  Either way, Tier-2/3 changes always still require human review at the PR.

### Where do the reports/tables actually show up?

- **CLI** (`kaizen run` / `kaizen fix` / `kaizen evaluate`) — pretty `rich`
  tables, including the treatment/control McNemar report. This is the
  primary place to read results.
- **Pull request body** — the same verdict/tier summary, as markdown, so
  reviewers see it without touching a terminal.
- **LangGraph Studio** (see below) is *not* a reporting dashboard — it shows
  live graph execution/state (useful for watching/approving an in-flight
  Tier-2 edit), not a rendered evaluation table. The raw report data is
  attached to the graph's state so it's inspectable there too, but the
  table itself lives in the CLI and the PR.

### Running LangGraph Studio

Note: Studio visualizes the **`langgraph` backend's** Fixer graph specifically
— there's no graph to visualize when `model.backend: copilot_cli` is active
(it's a plain subprocess call), so Studio is only useful if you've switched
a project to `langgraph`.

```bash
cp .env.example .env        # fill in ANTHROPIC_API_KEY / OPENAI_API_KEY / LANGSMITH_API_KEY etc.
export KAIZEN_CONFIG=/path/to/your/project/kaizen.yaml   # optional, defaults to the bundled example
poetry run langgraph dev
```
This opens LangGraph Studio against the **Fixer** graph (`kaizen.graphs:fixer_graph`,
declared in `langgraph.json`) — you can send it a prompt, watch each tool
call, and approve/reject Tier-2 code edits visually instead of (or in
addition to) the CLI's `y/N` prompt.

**`LANGSMITH_API_KEY`** (in `.env`) is optional but recommended: Studio works
without it, but you won't see the "Trace"/run-history tab populate. Free to
create at [smith.langchain.com](https://smith.langchain.com) → Settings →
API Keys. Without it, Studio shows a "LangSmith API key is missing" banner —
harmless, just no trace history.

### Prerequisite for the `copilot_cli` backend

Install the [GitHub Copilot CLI](https://docs.github.com/copilot/how-tos/use-copilot-agents/use-copilot-cli)
and run `copilot /login` once on the machine running Kaizen. No `.env`/API
key needed for this backend — it uses that login session.

## Development

```bash
poetry install
poetry run pytest
```

## Status

Core pieces (eval schema, trace store, .NET/pytest adapters, tiering, PR
gate, treatment/control evaluation, LangGraph-based Runner/Fixer agents,
Studio wiring) are implemented and tested. Try the bundled quickstart
above, or point it at a real target project with API keys configured.
