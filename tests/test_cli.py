import pytest
from typer.testing import CliRunner
from frontmatter_validator.cli import app
import yaml

runner = CliRunner()

@pytest.fixture
def mock_spec(tmp_path):
    spec_path = tmp_path / "specs.yaml"
    spec_content = {
        "universal": ["Category"],
        "categories": {
            "blog post": {"fields": ["Title", "Author", "Tags"]},
            "find": {"fields": ["Title", "URL"]}
        },
        "validations": [
            {
                "field": "Category",
                "value": "blog post",
                "require": ["Title"]
            }
        ]
    }
    spec_path.write_text(yaml.dump(spec_content))
    return spec_path

def test_validate_file_pass(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\nCategory: blog post\nTitle: My Post\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec)])
    assert result.exit_code == 0
    assert "PASS" in result.stdout

def test_validate_file_fail(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\nCategory: blog post\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec)])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "Field 'Title' is" in result.stdout

def test_validate_directory(mock_spec, tmp_path):
    (tmp_path / "dir1").mkdir()
    f1 = tmp_path / "dir1" / "p1.md"
    f1.write_text("---\nCategory: blog post\nTitle: P1\n---\nContent")
    f2 = tmp_path / "dir1" / "p2.md"
    f2.write_text("---\nCategory: find\nTitle: P2\n---\nContent")
    
    result = runner.invoke(app, [str(tmp_path / "dir1"), "--spec", str(mock_spec)])
    assert result.exit_code == 0
    assert "PASS" in result.stdout

def test_validate_path_not_found():
    result = runner.invoke(app, ["nonexistent.md"])
    assert result.exit_code == 1
    assert "Error: Path 'nonexistent.md' not found" in result.stdout

def test_validate_clean_dry_run(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\nCategory: blog post\nTitle: My Post\nExtra: field\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--clean", "--dry-run"])
    assert result.exit_code == 0
    # The output might have different formatting, let's just check for the key parts
    assert "CLEANED" in result.stdout or "Would remove" in result.stdout
    assert "Extra" in result.stdout
    
    # File should not be modified
    assert "Extra: field" in test_file.read_text()

def test_validate_clean_real(mock_spec, tmp_path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\nCategory: blog post\nTitle: My Post\nExtra: field\n---\nContent")
    
    result = runner.invoke(app, [str(test_file), "--spec", str(mock_spec), "--clean"])
    assert result.exit_code == 0
    assert "CLEANED" in result.stdout
    
    # File SHOULD be modified
    assert "Extra: field" not in test_file.read_text()
