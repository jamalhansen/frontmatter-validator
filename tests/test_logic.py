import pytest
from pathlib import Path
from frontmatter_validator.logic import validate_content, load_specs, clean_frontmatter

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
    is_valid, errors, suggestion, metadata = validate_content(content, specs, no_llm=True)
    assert is_valid, f"Validation failed with errors: {errors}"
    assert not errors

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
    is_valid, errors, suggestion, metadata = validate_content(content, specs, no_llm=True)
    assert not is_valid
    assert any("published_date" in e for e in errors)

def test_clean_frontmatter():
    metadata = {
        "Category": "blog post",
        "status": "draft",
        "extra_field": "remove me"
    }
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
    is_valid, errors, suggestion, metadata = validate_content(
        content, 
        specs, 
        no_llm=True, 
        template_fields=template_fields
    )
    assert is_valid, f"Validation failed with errors: {errors}"
