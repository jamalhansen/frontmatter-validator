import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
import frontmatter
from pydantic import ValidationError

from local_first_common.cli import resolve_provider
from local_first_common.tracking import register_tool, timed_run
from .schema import (
    UniversalFields,
    BlogPostFields,
    FindFields,
    NewsletterFields,
    StandaloneFields
)

_TOOL = register_tool("frontmatter-validator")

CATEGORY_MAP: Dict[str, Type[UniversalFields]] = {
    "blog post": BlogPostFields,
    "find": FindFields,
    "newsletter": NewsletterFields,
    "standalone": StandaloneFields,
}

def clean_category(category: str) -> str:
    """Clean category string (e.g. [[Blog Post]] -> blog post)."""
    cleaned = category.lower().strip("[]").strip()
    # Normalize variants
    if cleaned in ("blog post", "blog-post"):
        return "blog post"
    return cleaned

def get_fuzzy_suggestions(
    errors: List[Dict[str, Any]], 
    metadata: Dict[str, Any], 
    no_llm: bool = False,
    verbose: bool = False
) -> Optional[str]:
    """Use LLM to suggest fixes for validation errors."""
    if no_llm:
        return None

    try:
        llm = resolve_provider(no_llm=no_llm)
        system = "You are a helpful assistant that suggests fixes for YAML frontmatter validation errors."
        user = f"Validation failed for these fields:\n{errors}\n\nFrontmatter data:\n{metadata}\n\nSuggest specific fixes or common typos (e.g., 'did you mean article?'). Be extremely concise."
        
        if verbose:
            print("🧠 Asking LLM for fuzzy suggestions...")
            
        with timed_run("frontmatter-validator", llm.model) as _run:
            suggestion = llm.complete(system, user)
            _run.item_count = 1
            return suggestion.strip()
    except Exception as e:
        if verbose:
            print(f"⚠️  LLM suggestion failed: {e}")
        return None

def validate_content(
    content: str, 
    no_llm: bool = False, 
    verbose: bool = False
) -> Tuple[bool, List[str], Optional[str]]:
    """Validate markdown content frontmatter.
    Returns (is_valid, error_messages, fuzzy_suggestion).
    """
    try:
        post = frontmatter.loads(content)
        metadata = post.metadata
    except Exception as e:
        return False, [f"Failed to parse frontmatter: {e}"], None

    if "Category" not in metadata:
        return False, ["Missing 'Category' field"], None

    category_raw = metadata["Category"]
    category = clean_category(category_raw)
    
    schema_cls = CATEGORY_MAP.get(category)
    if not schema_cls:
        # Try fuzzy match with LLM?
        return False, [f"Unknown Category: '{category_raw}'"], None

    try:
        schema_cls.model_validate(metadata)
        return True, [], None
    except ValidationError as e:
        error_msgs = []
        for error in e.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            msg = error["msg"]
            error_msgs.append(f"{loc}: {msg}")
        
        suggestion = get_fuzzy_suggestions(e.errors(), metadata, no_llm=no_llm, verbose=verbose)
        return False, error_msgs, suggestion
