import subprocess

from click.testing import CliRunner

from kaizen.cli import main
from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalSuite
from kaizen.init import detect_adapter, detect_default_branch, scaffold


def test_detect_adapter_pytest(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n")
    assert detect_adapter(tmp_path) == "pytest"


def test_detect_adapter_dotnet(tmp_path):
    (tmp_path / "MyProj.csproj").write_text("<Project />")
    assert detect_adapter(tmp_path) == "dotnet"


def test_detect_adapter_none_when_unrecognized(tmp_path):
    (tmp_path / "README.md").write_text("hello")
    assert detect_adapter(tmp_path) is None


def test_detect_default_branch_outside_git_repo(tmp_path):
    assert detect_default_branch(tmp_path) == "main"


def test_detect_default_branch_from_current_branch(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "trunk"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=tmp_path, check=True)
    (tmp_path / "f").write_text("x")
    subprocess.run(["git", "add", "f"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=tmp_path, check=True)
    assert detect_default_branch(tmp_path) == "trunk"


def test_scaffold_writes_loadable_config(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n")
    kaizen_yaml = scaffold(tmp_path, "pytest")

    config = KaizenConfig.load(kaizen_yaml)
    assert config.adapter.name == "pytest"
    assert config.repo_path == str(tmp_path.resolve())
    assert config.model.backend == "copilot_cli"

    suite = EvalSuite.load(f"{config.repo_path}/{config.eval_suite_path}")
    assert len(suite.cases) == 1
    assert suite.cases[0].command == ["pytest"]


def test_scaffold_dotnet_eval_command(tmp_path):
    kaizen_yaml = scaffold(tmp_path, "dotnet")
    suite = EvalSuite.load(tmp_path / "evals")
    assert suite.cases[0].command == ["dotnet", "test"]
    assert kaizen_yaml.exists()


def test_cli_init_detects_and_scaffolds(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n")
    result = CliRunner().invoke(main, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "adapter=pytest" in result.output
    assert (tmp_path / "kaizen.yaml").exists()


def test_cli_init_refuses_to_overwrite_without_force(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n")
    (tmp_path / "kaizen.yaml").write_text("existing: true\n")
    result = CliRunner().invoke(main, ["init", str(tmp_path)])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_cli_init_fails_clearly_when_undetectable(tmp_path):
    result = CliRunner().invoke(main, ["init", str(tmp_path)])
    assert result.exit_code != 0
    assert "Couldn't detect a project type" in result.output
