# Contributing

Contributions are welcome — bug fixes, a new `ProjectAdapter` for another
language/ecosystem, documentation improvements, or anything in between.

## Development

```bash
poetry install
poetry run pytest
```

See the README's [Quickstart](README.md#quickstart-5-minutes-no-target-project-of-your-own-needed)
for a working example to develop against.

## Opening a PR

- Keep changes focused — small, reviewable PRs over large ones.
- Add a test for new behavior where practical; `poetry run pytest` should
  pass before you open the PR (CI runs it too).
- Describe the *why*, not just the *what*, in the PR description.
