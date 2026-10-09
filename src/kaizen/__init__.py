"""KaizenAI: a closed-loop, self-improving agent framework.

A Runner agent executes a project's eval suite (via MCP or shell), a Fixer
agent analyzes the resulting failures and proposes minimal, scoped patches,
and every patch passes through a human-approval gate (PR) before merging.
"""

__version__ = "0.1.0"
