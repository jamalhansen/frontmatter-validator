import pytest
from pathlib import Path
from frontmatter_validator.logic import (
    FrontmatterParseError,
    SpecLoadError,
    ValidationResult,
    clean_frontmatter,
    load_specs,
    load_specs_or_raise,
    parse_frontmatter_or_raise,
    validate_content,
)


@pytest.fixture
def specs():
    return load_specs(Path("specs.yaml"))


def test_validate_blog_post_valid(specs):
    content = """---
Category: "[[Blog Post]]"
status: draft
created: 2026-03-26
published_date: ""
canonical_url: ""
tags: []
title: "My First Post"
---
# Hello World
"""
    result = validate_content(content, specs, no_llm=True)
    assert isinstance(result, ValidationResult)
    assert result.is_valid, f"Validation failed with errors: {result.errors}"
    assert not result.errors


def test_validate_published_missing_date(specs):
    content = """---
Category: "blog post"
status: published
created: 2026-03-26
canonical_url: ""
tags: []
title: "My Published Post"
---
"""
    # Note: published_date is missing
    result = validate_content(content, specs, no_llm=True)
    assert not result.is_valid
    assert any("published_date" in e for e in result.errors)


def test_clean_frontmatter():
    metadata = {"Category": "blog post", "status": "draft", "extra_field": "remove me"}
    allowed = {"Category", "status"}
    cleaned = clean_frontmatter(metadata, allowed)
    assert "Category" in cleaned
    assert "status" in cleaned
    assert "extra_field" not in cleaned


def test_validate_with_template_fields(specs):
    content = """---
Category: "blog post"
status: draft
created: 2026-03-26
published_date: ""
canonical_url: ""
tags: []
template_specific: "value"
---
"""
    template_fields = {"template_specific"}
    result = validate_content(
        content, specs, no_llm=True, template_fields=template_fields
    )
    assert result.is_valid, f"Validation failed with errors: {result.errors}"


def test_conditional_validation_logic(specs):
    # Test that status: published requires published_date
    content = """---
Category: "blog post"
status: published
created: 2026-03-26
canonical_url: ""
tags: []
title: "Missing date"
---
"""
    result = validate_content(content, specs, no_llm=True)
    assert not result.is_valid
    assert any("published_date" in e for e in result.errors)

    # Add the missing date
    content_with_date = content.replace(
        'published_date: ""', "published_date: 2026-03-26"
    )
    if "published_date:" not in content:
        content_with_date = content.replace(
            "status: published", "status: published\npublished_date: 2026-03-26"
        )

    result2 = validate_content(content_with_date, specs, no_llm=True)
    assert result2.is_valid, f"Should be valid now: {result2.errors}"


def test_load_specs_or_raise_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("[unclosed")

    with pytest.raises(SpecLoadError):
        load_specs_or_raise(bad)


def test_parse_frontmatter_or_raise_invalid_content():
    bad_content = "---\ncategory: [\n---\ntext"

    with pytest.raises(FrontmatterParseError):
        parse_frontmatter_or_raise(bad_content)
