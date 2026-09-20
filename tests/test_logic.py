from pathlib import Path

import pytest

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
category: "[[Blog Post]]"
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
category: "blog post"
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
    metadata = {"category": "blog post", "status": "draft", "extra_field": "remove me"}
    allowed = {"category", "status"}
    cleaned = clean_frontmatter(metadata, allowed)
    assert "category" in cleaned
    assert "status" in cleaned
    assert "extra_field" not in cleaned


def test_validate_with_template_fields(specs):
    content = """---
category: "blog post"
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
    # Test that status: published requires published_date and canonical_url
    content = """---
category: "blog post"
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
    assert any("canonical_url" in e for e in result.errors)

    # Add the missing fields
    content_with_date = content.replace(
        'canonical_url: ""',
        'canonical_url: "https://example.com/post"\npublished_date: 2026-03-26',
    )

    result2 = validate_content(content_with_date, specs, no_llm=True)
    assert result2.is_valid, f"Should be valid now: {result2.errors}"


def test_draft_status_does_not_require_published_date_or_canonical_url(specs):
    """Regression 2026-09-20: published_date and canonical_url used to be
    listed as universal (required for every item regardless of status) --
    real content showed ~95% of the resulting violations were on drafts,
    outlines, and ideas that were never meant to have either yet. Both are
    now conditional on status: published only, matching how the spec
    already treated this distinction in principle."""
    content = """---
category: "blog post"
status: draft
created: 2026-03-26
tags: []
title: "A draft post"
---
"""
    result = validate_content(content, specs, no_llm=True)
    assert result.is_valid, f"A draft should not need published_date/canonical_url: {result.errors}"


def test_load_specs_or_raise_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("[unclosed")

    with pytest.raises(SpecLoadError):
        load_specs_or_raise(bad)


def test_parse_frontmatter_or_raise_invalid_content():
    bad_content = "---\ncategory: [\n---\ntext"

    with pytest.raises(FrontmatterParseError):
        parse_frontmatter_or_raise(bad_content)
