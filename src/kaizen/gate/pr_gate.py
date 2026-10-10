"""Human-in-the-loop PR gate.

Every patch the Fixer produces - regardless of tier - goes through a PR, not
a direct commit to the base branch. Tier only controls the messaging/urgency
and (optionally, per config) whether Tier-1 PRs can be auto-merged once CI +
the re-verified eval case both pass; Tier-2/3 always require manual review.
"""
from __future__ import annotations

import subprocess

from kaizen.config import KaizenConfig, PatchTier
from kaizen.fixer.agent import PatchPlan

_TIER_LABELS = {
    PatchTier.TIER_1_SAFE: "kaizen:tier-1-safe",
    PatchTier.TIER_2_CODE: "kaizen:tier-2-code",
    PatchTier.TIER_3_LOCKED: "kaizen:tier-3-locked",
}


def _pr_create_url_fallback(repo_path: str, branch_name: str) -> str:
    """Builds the "create a PR" URL directly from the `origin` remote, for
    when the `gh` CLI isn't installed/authenticated - git already prints
    this same URL after a push; this makes it available programmatically
    too instead of crashing.
    """
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=repo_path, capture_output=True, text=True, check=True
    )
    remote = result.stdout.strip()
    if remote.startswith("git@"):
        host, _, path = remote[len("git@"):].partition(":")
    else:
        host, _, path = remote.split("://", 1)[-1].partition("/")
    path = path.removesuffix(".git")
    return f"https://{host}/{path}/pull/new/{branch_name}"


def open_pr(config: KaizenConfig, plan: PatchPlan) -> str:
    """Commits the working tree on ``plan.branch_name`` and opens a PR.

    Uses the GitHub CLI (`gh`) if it's installed and authenticated. If not
    (or if `gh pr create` fails for any other reason), falls back to
    returning the same "create a PR" URL git already prints after a push -
    the branch is still pushed either way, so nothing is lost; you just
    open the PR manually instead of it being created for you.
    """
    repo = config.repo_path

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"kaizen: {plan.summary}"],
        cwd=repo, check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", plan.branch_name],
        cwd=repo, check=True,
    )

    verified = "yes" if plan.verified_fixed else "NO - needs manual verification"
    verdict_line = f"- Evaluation verdict: `{plan.verdict}`\n" if plan.verdict else ""
    body = (
        f"### Kaizen auto-generated fix\n\n"
        f"- Failing eval case: `{plan.case_id}`\n"
        f"- Risk tier: `{plan.highest_tier.value}`\n"
        f"{verdict_line}"
        f"- Files touched: {', '.join(plan.files_touched) or '(none detected)'}\n"
        f"- Re-verified locally: {verified}\n\n"
        f"This PR was opened automatically and requires human review before merge.\n"
    )

    try:
        result = subprocess.run(
            [
                "gh", "pr", "create",
                "--base", config.gate.base_branch,
                "--head", plan.branch_name,
                "--title", f"kaizen: fix {plan.case_id}",
                "--body", body,
                "--label", _TIER_LABELS[plan.highest_tier],
            ],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        url = _pr_create_url_fallback(repo, plan.branch_name)
        return f"{url}  ('gh' CLI not installed - open this URL manually to create the PR)"
    except subprocess.CalledProcessError as exc:
        url = _pr_create_url_fallback(repo, plan.branch_name)
        detail = exc.stderr.strip() if exc.stderr else str(exc)
        return f"{url}  ('gh pr create' failed ({detail}) - open this URL manually to create the PR)"
