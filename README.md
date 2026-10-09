# KaizenAI

**Kaizen (改善)**: continuous, incremental improvement. This repo is a
Python, MCP-native agent framework for closed-loop, self-improving software
testing and maintenance — built so it can be pointed at *any* project
without changes to the framework itself.

## How it works

1. **Runner agent** connects to a target project (via shell commands and/or
   its MCP server) and executes that project's **eval suite** — a small set
   of representative tasks with clear pass/fail criteria.
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

## Adding a new target project

1. Add a `kaizen.yaml` to the target repo (see
   `examples/sample_dotnet_project/kaizen.yaml`).
2. Add an `evals/` directory with one `*.eval.yaml` file per case (see
   `examples/sample_dotnet_project/evals/`).
3. Run:
   ```bash
   kaizen run --config path/to/kaizen.yaml
   kaizen fix --config path/to/kaizen.yaml --open-pr
   ```

## Risk tiers

| Tier | Scope | Review |
|---|---|---|
| 1 — safe | prompts, tool descriptions, eval/config files, docs | lightweight |
| 2 — code | application source code | always required |
| 3 — locked | secrets, infra, CI/CD config | Fixer may never modify |

## Development

```bash
poetry install
poetry run pytest
```

## Status

Early scaffold. Core pieces (eval schema, trace store, .NET adapter, tiering,
PR gate) are implemented and tested; the Runner/Fixer agent LLM integration
uses the [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) and
is ready to exercise end-to-end once pointed at a real target project.
