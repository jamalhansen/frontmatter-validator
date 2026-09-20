import pytest
import yaml
from typer.testing import CliRunner

from frontmatter_validator.cli import app

runner = CliRunner()

@pytest.fixture
def mock_spec(tmp_path):
    spec_path = tmp_path / "specs.yaml"
    spec_content = {
        "universal": ["category"],
        "categories": {
            "blog post": {"fields": ["Title", "Author", "Tags"]},
            "find": {"fields": ["Title", "URL"]}
        },
        "validations": [
            {
                "field": "category",
                "value": "blog post",
                "require": ["Title"]
            }
        ]
    }
    spec_path.write_text(yaml.dump(spec_content))
    return spec_path

def test_validate_file_pass(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec)])
    assert result.exit_code == 0
    assert "PASS" in result.stdout

def test_validate_file_fail(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec)])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "Field 'Title' is" in result.stdout

def test_validate_directory(mock_spec, tmp_path):
    (tmp_path / "dir1").mkdir()
    f1 = tmp_path / "dir1" / "p1.md"
    f1.write_text("---\ncategory: blog post\nTitle: P1\n---\nContent")
    f2 = tmp_path / "dir1" / "p2.md"
    f2.write_text("---\ncategory: find\nTitle: P2\n---\nContent")
    
    result = runner.invoke(app, [str(tmp_path / "dir1"), "--spec", str(mock_spec)])
    assert result.exit_code == 0
    assert "PASS" in result.stdout

def test_validate_path_not_found():
    result = runner.invoke(app, ["nonexistent.md"])
    assert result.exit_code == 1
    assert "Error: Path 'nonexistent.md' not found" in result.stdout

def test_validate_clean_dry_run(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\nExtra: field\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--clean", "--dry-run"])
    assert result.exit_code == 0
    # The output might have different formatting, let's just check for the key parts
    assert "CLEANED" in result.stdout or "Would remove" in result.stdout
    assert "Extra" in result.stdout
    
    # File should not be modified
    assert "Extra: field" in test_file.read_text()

def test_validate_clean_real(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\nExtra: field\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--clean"])
    assert result.exit_code == 0
    assert "CLEANED" in result.stdout
    
    # File SHOULD be modified
    assert "Extra: field" not in test_file.read_text()


def test_validate_clean_real_with_no_llm_still_writes(mock_spec, tmp_path):
    """Regression 2026-09-20: this tool's write actions (--clean,
    --fill-defaults) are deterministic, not LLM-derived, so --no-llm must
    NOT silently force dry-run here the way it does fleet-wide for tools
    whose writes come from LLM output. Found live: a real --fill-defaults
    run against BrainSync with --no-llm (needed to skip suggestion
    generation) wrote nothing at all."""
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\nExtra: field\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--clean", "--no-llm"])
    assert result.exit_code == 0
    assert "Extra: field" not in test_file.read_text()


def test_validate_fill_defaults_dry_run(mock_spec, tmp_path):
    test_file = tmp_path / "2026-04-04-test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--fill-defaults", "--dry-run"])
    assert result.exit_code == 0
    assert "files filled" not in result.stdout

    # File should not be modified
    assert "created" not in test_file.read_text()


def test_validate_fill_defaults_real_writes_created_from_filename(mock_spec, tmp_path):
    test_file = tmp_path / "2026-04-04-test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--fill-defaults"])
    assert result.exit_code == 0
    assert "1 files filled" in result.stdout

    written = test_file.read_text()
    assert "created: 2026-04-04" in written


def test_validate_fill_defaults_with_no_llm_still_writes(mock_spec, tmp_path):
    """Same regression as --clean: --no-llm must not force dry-run for this
    tool's deterministic write actions."""
    test_file = tmp_path / "2026-04-04-test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--fill-defaults", "--no-llm"])
    assert result.exit_code == 0
    assert "created: 2026-04-04" in test_file.read_text()


def test_validate_fill_defaults_falls_back_to_mtime_without_date_prefix(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--fill-defaults"])
    assert result.exit_code == 0
    assert "1 files filled" in result.stdout
    assert "created:" in test_file.read_text()


def test_validate_fill_defaults_does_not_touch_existing_created(mock_spec, tmp_path):
    test_file = tmp_path / "2026-04-04-test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\ncreated: 2020-01-01\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--fill-defaults"])
    assert result.exit_code == 0
    assert "files filled" not in result.stdout
    assert "created: 2020-01-01" in test_file.read_text()


def test_validate_pipe_and_json(mock_spec, tmp_path):
    content = "---\ncategory: blog post\nTitle: Piped Post\n---\nPiped content"
    
    # Test pipe pass
    res_pipe = runner.invoke(app, ["-", "--spec", str(mock_spec)], input=content)
    assert res_pipe.exit_code == 0
    assert "Piped content" in res_pipe.stdout

    # Test json output
    test_file = tmp_path / "test.md"
    test_file.write_text(content)
    res_json = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--json"])
    assert res_json.exit_code == 0
    assert '"is_valid": true' in res_json.stdout


def test_validate_json_with_real_date_field_does_not_crash(mock_spec, tmp_path):
    """Regression: PyYAML parses an unquoted YAML date (e.g. "created:
    2026-04-15") into a real datetime.date object, and json.dumps() can't
    serialize that without a default= handler. Every real post has a
    created/published_date field -- --json has likely never worked on real
    content before this fix. Exercised in both the single-file and
    directory-walk branches, since they build their JSON payload separately."""
    content = "---\ncategory: blog post\nTitle: Dated Post\ncreated: 2026-04-15\n---\nContent"

    test_file = tmp_path / "test.md"
    test_file.write_text(content)
    res_file = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--json"])
    assert res_file.exit_code == 0
    assert "not JSON serializable" not in res_file.output
    assert '"created": "2026-04-15"' in res_file.stdout

    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1" / "p1.md").write_text(content)
    res_dir = runner.invoke(app, [str(tmp_path / "dir1"), "--spec", str(mock_spec), "--json"])
    assert res_dir.exit_code == 0
    assert "not JSON serializable" not in res_dir.output
    assert '"created": "2026-04-15"' in res_dir.stdout


def test_validate_lowercase_category_passes(mock_spec, tmp_path):
    """Regression 2026-09-20: the field check used to hardcode "Category"
    (capital C), but real vault content consistently uses lowercase
    "category:" -- a Python dict lookup by exact key, so every real file
    failed with "Missing 'Category' field" regardless of actual validity.
    Confirmed against real BrainSync content before this fix: 306/306 files
    flagged invalid, 100% false positives."""
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ncategory: blog post\nTitle: My Post\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec)])
    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_validate_uppercase_category_key_is_a_real_distinct_yaml_key(mock_spec, tmp_path):
    """Documents the real behavior, not just asserts it: YAML/dict keys are
    case-sensitive, so "Category:" and "category:" are genuinely different
    keys -- this isn't case-INsensitive matching, the spec and check were
    just changed to match what real content actually uses."""
    test_file = tmp_path / "test.md"
    test_file.write_text("---\nCategory: blog post\nTitle: My Post\n---\nContent")

    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec)])
    assert result.exit_code == 1
    assert "Missing 'category' field" in result.stdout

