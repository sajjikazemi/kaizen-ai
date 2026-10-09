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
2. Add an `evals/` directory with one `*.eval.yaml` file per case, tagged
   by feature area (see `examples/sample_dotnet_project/evals/`).
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
