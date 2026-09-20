"""Eval get_fuzzy_suggestions() against objectively-known-correct answers.

This tool defaults to llama3.2:3b -- the same model that scored an 82% false-dismiss
rate on content-discovery-agent's scoring task (2026-09-13/14). That result doesn't
transfer here automatically: unlike content-discovery-agent's scoring, where "correct"
means matching Claude's subjective judgment, a missing-field suggestion here has an
objectively correct answer straight from specs.yaml -- no Claude ground truth needed,
no subjective judgment call. This eval exists to prove that, not assume it.

Fixtures reflect the actual error shapes validate_content() produces (checked against
core.py 2026-09-14): missing 'category', a missing universal field, or status=published
without published_date. NOT category-name typos -- clean_category() doesn't currently
flag an unrecognized category as an error, so that's not a real code path today despite
the LLM prompt's "did you mean article?" example suggesting otherwise.
"""

from dataclasses import dataclass

from frontmatter_validator.core import get_fuzzy_suggestions


@dataclass
class Fixture:
    name: str
    errors: list[str]
    metadata: dict
    expected_keyword: str  # the correct fix must mention this, case-insensitive substring match


FIXTURES = [
    Fixture(
        name="missing_category",
        errors=["Missing 'category' field"],
        metadata={"status": "draft", "created": "2026-09-14"},
        expected_keyword="category",
    ),
    Fixture(
        name="missing_status",
        errors=["Missing universal field: 'status'"],
        metadata={"category": "blog post", "created": "2026-09-14"},
        expected_keyword="status",
    ),
    Fixture(
        name="missing_tags",
        errors=["Missing universal field: 'tags'"],
        metadata={"category": "find", "status": "kept", "created": "2026-09-14"},
        expected_keyword="tags",
    ),
    Fixture(
        name="missing_canonical_url",
        errors=["Missing universal field: 'canonical_url'"],
        metadata={"category": "blog post", "status": "published", "created": "2026-09-14"},
        expected_keyword="canonical_url",
    ),
    Fixture(
        name="published_missing_date",
        errors=["'published_date' is required when status is 'published'"],
        metadata={"category": "blog post", "status": "published", "created": "2026-09-14"},
        expected_keyword="published_date",
    ),
]


def run_eval(model: str) -> None:
    print(f"Model: {model}\n")

    n_correct = 0
    for fx in FIXTURES:
        suggestion = get_fuzzy_suggestions(fx.errors, fx.metadata, verbose=False, model=model)
        correct = bool(suggestion) and fx.expected_keyword.lower() in suggestion.lower()
        n_correct += correct
        mark = "OK" if correct else "MISS"
        print(f"[{mark}] {fx.name}")
        print(f"       errors: {fx.errors}")
        print(f"       suggestion: {suggestion!r}")
        print()

    print(f"{n_correct}/{len(FIXTURES)} correct (mentions the actual missing field)")


if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    run_eval(model)
