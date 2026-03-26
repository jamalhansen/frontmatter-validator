import pytest
from frontmatter_validator.logic import validate_content

def test_validate_blog_post_valid():
    content = """---
Category: "[[Blog Post]]"
status: draft
created: 2026-03-26
title: "My First Post"
---
# Hello World
"""
    is_valid, errors, suggestion = validate_content(content, no_llm=True)
    assert is_valid
    assert not errors

def test_validate_published_missing_date():
    content = """---
Category: "blog post"
status: published
title: "My Published Post"
---
"""
    is_valid, errors, suggestion = validate_content(content, no_llm=True)
    assert not is_valid
    assert any("published_date" in e for e in errors)

def test_validate_unknown_category():
    content = """---
Category: "Unknown"
status: idea
---
"""
    is_valid, errors, suggestion = validate_content(content, no_llm=True)
    assert not is_valid
    assert "Unknown Category" in errors[0]

def test_validate_find_valid():
    content = """---
Category: "find"
status: idea
source_url: "https://example.com"
source_title: "Example"
source_type: "article"
---
"""
    is_valid, errors, suggestion = validate_content(content, no_llm=True)
    assert is_valid
