from unittest.mock import patch

from frontmatter_validator.eval_suggestions import FIXTURES, run_eval


def test_fixtures_cover_the_real_error_shapes_validate_content_produces():
    # Guards against the eval drifting from what the tool actually does --
    # these three shapes are the only ones validate_content() raises today.
    error_texts = " ".join(" ".join(fx.errors) for fx in FIXTURES)
    assert "Missing 'Category' field" in error_texts
    assert "Missing universal field" in error_texts
    assert "published_date" in error_texts


def test_run_eval_counts_keyword_matches_as_correct(capsys):
    with patch(
        "frontmatter_validator.eval_suggestions.get_fuzzy_suggestions",
        return_value="Add the missing category field to fix this.",
    ):
        run_eval("fake-model")
    out = capsys.readouterr().out
    # Only fixtures whose expected_keyword is "category" should show OK with this canned response
    assert "[OK] missing_category" in out
    assert "[MISS] missing_status" in out


def test_run_eval_handles_none_suggestion(capsys):
    with patch("frontmatter_validator.eval_suggestions.get_fuzzy_suggestions", return_value=None):
        run_eval("fake-model")
    out = capsys.readouterr().out
    assert "0/5 correct" in out
