from kaizen.config import PatchTier
from kaizen.fixer.tiering import classify_tier


def test_tier3_locked_paths():
    assert classify_tier("infra/main.tf") == PatchTier.TIER_3_LOCKED
    assert classify_tier(".github/workflows/ci.yml") == PatchTier.TIER_3_LOCKED
    assert classify_tier("secrets/db.pem") == PatchTier.TIER_3_LOCKED


def test_tier1_safe_paths():
    assert classify_tier("prompts/system.md") == PatchTier.TIER_1_SAFE
    assert classify_tier("evals/build.eval.yaml") == PatchTier.TIER_1_SAFE
    assert classify_tier("README.md") == PatchTier.TIER_1_SAFE


def test_tier2_default_for_code():
    assert classify_tier("src/Program.cs") == PatchTier.TIER_2_CODE
