from local_first_common.config import get_setting
from local_first_common.cli import init_config_option
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import frontmatter
import yaml

from pydantic import BaseModel
from local_first_common.cli import resolve_provider
from local_first_common.tracking import register_tool, timed_run

_TOOL = register_tool("frontmatter-validator")
TOOL_NAME = "frontmatter-validator"
DEFAULTS = {"provider": "ollama", "model": "llama3"}

class ValidationResult(BaseModel):
    """Result of frontmatter validation."""
    is_valid: bool
    errors: List[str]
    suggestion: Optional[str] = None
    metadata: Dict[str, Any]

def load_specs(specs_path: Path = Path("specs.yaml")) -> Dict[str, Any]:
    """Load validation specs from YAML."""
    if not specs_path.exists():
        # Default empty spec if file missing
        return {"universal": [], "categories": {}, "validations": []}
    with open(specs_path, "r") as f:
        return yaml.safe_load(f)

def clean_category(category: str, specs: Dict[str, Any]) -> str:
    """Find the canonical category name from a string (including aliases)."""
    val = category.lower().strip()
    
    # Check aliases in specs
    for cat_name, info in specs.get("categories", {}).items():
        aliases = [a.lower() for a in info.get("aliases", [])]
        if val == cat_name.lower() or val in aliases:
            return cat_name
            
    # Fallback to simple cleaning
    return val.strip("[]").strip().lower()

def get_allowed_fields(category: str, specs: Dict[str, Any]) -> Set[str]:
    """Get the set of all allowed fields for a category."""
    allowed = set(specs.get("universal", []))
    cat_info = specs.get("categories", {}).get(category, {})
    allowed.update(cat_info.get("fields", []))
    return allowed

def get_fuzzy_suggestions(
    errors: List[str], 
    metadata: Dict[str, Any], 
    no_llm: bool = False,
    verbose: bool = False
) -> Optional[str]:
    """Use LLM to suggest fixes for validation errors."""
    if no_llm:
        return None

    try:
        actual_provider = get_setting(TOOL_NAME, "provider", cli_val=provider, default="ollama")
    actual_model = get_setting(TOOL_NAME, "model", cli_val=model)
    llm = resolve_provider(no_llm=no_llm)
        system = "You are a helpful assistant that suggests fixes for YAML frontmatter validation errors."
        user = f"Validation failed with these errors:\n{errors}\n\nFrontmatter data:\n{metadata}\n\nSuggest specific fixes or common typos (e.g., 'did you mean article?'). Be extremely concise."
        
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
    specs: Dict[str, Any],
    no_llm: bool = False, 
    verbose: bool = False,
    template_fields: Optional[Set[str]] = None
) -> ValidationResult:
    """Validate markdown content frontmatter.
    Returns a ValidationResult object.
    """
    try:
        post = frontmatter.loads(content)
        metadata = post.metadata
    except Exception as e:
        return ValidationResult(
            is_valid=False, 
            errors=[f"Failed to parse frontmatter: {e}"], 
            metadata={}
        )

    errors = []
    
    if "Category" not in metadata:
        errors.append("Missing 'Category' field")
        return ValidationResult(
            is_valid=False, 
            errors=errors, 
            metadata=metadata
        )

    category_raw = metadata["Category"]
    category = clean_category(category_raw, specs)
    
    allowed_fields = get_allowed_fields(category, specs)
    if template_fields:
        # If template provided, ensure ALL template fields are present? 
        # Or at least allow them. 
        allowed_fields.update(template_fields)

    # 1. Check required universal fields
    for field in specs.get("universal", []):
        if field not in metadata:
            errors.append(f"Missing universal field: '{field}'")

    # 2. Check category fields (optional for now, or we can define them as required in specs if needed)
    # For now, let's just use the allowed set to flag "Unknown" fields if we want, but 
    # validation is mostly about ensuring required fields exist.
    
    # 3. Custom Validations
    for v in specs.get("validations", []):
        field = v.get("field")
        val = v.get("value")
        required_fields = v.get("require", [])
        
        if metadata.get(field) == val:
            for rf in required_fields:
                if not metadata.get(rf):
                    errors.append(f"Field '{rf}' is required when '{field}' is '{val}'")

    suggestion = None
    if errors:
        suggestion = get_fuzzy_suggestions(errors, metadata, no_llm=no_llm, verbose=verbose)
        
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        suggestion=suggestion,
        metadata=metadata
    )

def clean_frontmatter(metadata: Dict[str, Any], allowed_fields: Set[str]) -> Dict[str, Any]:
    """Remove fields NOT in the allowed set."""
    return {k: v for k, v in metadata.items() if k in allowed_fields}

def get_template_fields(template_path: Path) -> Set[str]:
    """Extract frontmatter field names from an Obsidian template."""
    if not template_path.exists():
        return set()
    try:
        content = template_path.read_text(encoding="utf-8")
        post = frontmatter.loads(content)
        return set(post.metadata.keys())
    except Exception:
        return set()