from kaizen.fixer.tools import make_fixer_tools


def test_write_file_denies_tier3_path(tmp_path):
    touched: list[str] = []
    tools = make_fixer_tools(str(tmp_path), touched)
    write_file = next(t for t in tools if t.name == "write_file")

    result = write_file.invoke({"path": "infra/main.tf", "content": "x"})

    assert "DENIED" in result
    assert touched == []
    assert not (tmp_path / "infra" / "main.tf").exists()


def test_write_file_allows_tier1_and_tier2_paths(tmp_path):
    touched: list[str] = []
    tools = make_fixer_tools(str(tmp_path), touched)
    write_file = next(t for t in tools if t.name == "write_file")

    write_file.invoke({"path": "src/Program.cs", "content": "// ok"})
    write_file.invoke({"path": "prompts/system.md", "content": "# ok"})

    assert touched == ["src/Program.cs", "prompts/system.md"]
    assert (tmp_path / "src" / "Program.cs").read_text() == "// ok"


def test_edit_file_denies_tier3_and_errors_on_missing_text(tmp_path):
    touched: list[str] = []
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "db.pem").write_text("ORIGINAL")
    (tmp_path / "Program.cs").write_text("hello world")

    tools = make_fixer_tools(str(tmp_path), touched)
    edit_file = next(t for t in tools if t.name == "edit_file")

    denied = edit_file.invoke({"path": "secrets/db.pem", "old_str": "ORIGINAL", "new_str": "X"})
    assert "DENIED" in denied
    assert (tmp_path / "secrets" / "db.pem").read_text() == "ORIGINAL"

    not_found = edit_file.invoke({"path": "Program.cs", "old_str": "NOPE", "new_str": "X"})
    assert "ERROR" in not_found

    ok = edit_file.invoke({"path": "Program.cs", "old_str": "hello", "new_str": "goodbye"})
    assert "Edited" in ok
    assert (tmp_path / "Program.cs").read_text() == "goodbye world"
    assert touched == ["Program.cs"]


def test_read_file_rejects_path_escaping_repo_root(tmp_path):
    import pytest

    touched: list[str] = []
    tools = make_fixer_tools(str(tmp_path), touched)
    read_file = next(t for t in tools if t.name == "read_file")

    with pytest.raises(Exception, match="escapes the repository root"):
        read_file.invoke({"path": "../outside.txt"})
