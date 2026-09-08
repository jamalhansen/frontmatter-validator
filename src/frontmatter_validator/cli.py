import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import frontmatter
import typer
from rich.console import Console
from rich.table import Table

from local_first_common.cli import (
    init_config_option,
    dry_run_option,
    no_llm_option,
    verbose_option,
    pipe_option,
    json_option,
    resolve_dry_run,
)
from local_first_common.logging import setup_logging
from .core import (
    FrontmatterParseError,
    SpecLoadError,
    parse_frontmatter_or_raise,
    load_specs,
    validate_content,
    clean_frontmatter,
    get_template_fields,
    clean_category,
    get_allowed_fields,
)

TOOL_NAME = "frontmatter-validator"
DEFAULTS = {"provider": "ollama", "model": "llama3"}

app = typer.Typer(help="Content Frontmatter Validator")
console = Console()

TEMPLATE_MAP = {
    "blog post": "Blog Post.md",
    "find": "Find.md",
    "newsletter": "Newsletter.md",
}


@app.command()
def validate(
    path: Annotated[
        Optional[Path],
        typer.Argument(help="File or directory to validate (or '-' for stdin)"),
    ] = None,
    spec: Optional[Path] = typer.Option(
        Path("specs.yaml"), "--spec", help="Path to custom validation spec YAML"
    ),
    template_dir: Optional[Path] = typer.Option(
        None, "--template-dir", help="Path to Obsidian templates directory"
    ),
    clean: bool = typer.Option(
        False, "--clean", help="Remove unused frontmatter fields NOT in spec"
    ),
    pipe: Annotated[bool, pipe_option()] = False,
    json_output: Annotated[bool, json_option()] = False,
    dry_run: Annotated[bool, dry_run_option()] = False,
    no_llm: Annotated[bool, no_llm_option()] = False,
    verbose: Annotated[bool, verbose_option()] = False,
    init_config: Annotated[bool, init_config_option(TOOL_NAME, DEFAULTS)] = False,
):
    """Validate Obsidian markdown frontmatter against Content Format Spec."""
    dry_run = resolve_dry_run(dry_run, no_llm)

    log_level = logging.DEBUG if verbose else logging.WARNING
    setup_logging(level=log_level, tool_name=TOOL_NAME, persist_warnings=True)

    try:
        specs = load_specs(spec)
    except SpecLoadError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    is_pipe = pipe or (path is not None and str(path) == "-")

    if is_pipe:
        content = sys.stdin.read()
        try:
            post = parse_frontmatter_or_raise(content)
        except FrontmatterParseError:
            post = frontmatter.Post("", **{})
        category_raw = post.metadata.get("Category", "")
        category = clean_category(category_raw, specs)

        template_fields = None
        if template_dir and category in TEMPLATE_MAP:
            template_path = template_dir / TEMPLATE_MAP[category]
            if template_path.exists():
                template_fields = get_template_fields(template_path)

        result = validate_content(
            content,
            specs,
            no_llm=no_llm,
            verbose=verbose,
            template_fields=template_fields,
        )

        output_content = content
        if clean:
            allowed = get_allowed_fields(category, specs)
            if template_fields:
                allowed.update(template_fields)
            cleaned_metadata = clean_frontmatter(result.metadata, allowed)
            post.metadata = cleaned_metadata
            output_content = frontmatter.dumps(post)

        if json_output:
            print(
                json.dumps(
                    {
                        "is_valid": result.is_valid,
                        "errors": result.errors,
                        "metadata": result.metadata,
                        "suggestion": result.suggestion,
                    },
                    indent=2,
                )
            )
            if not result.is_valid:
                raise typer.Exit(1)
            return

        if result.is_valid:
            sys.stdout.write(output_content)
        else:
            sys.stderr.write(f"Validation failed: {', '.join(result.errors)}\n")
            raise typer.Exit(1)
        return

    if path is None:
        typer.secho(
            "Error: Missing file or directory path (or '-' for stdin).",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = list(path.rglob("*.md"))
    else:
        typer.secho(f"Error: Path '{path}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not files:
        typer.echo("No markdown files found.")
        return

    table = Table(title="Validation Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Errors", style="red")
    table.add_column("Actions", style="yellow")
    table.add_column("Suggestions", style="green")

    valid_count = 0
    invalid_count = 0
    cleaned_count = 0
    results_json = []

    for file in files:
        content = file.read_text(encoding="utf-8")

        # Determine category for template lookup
        try:
            post = parse_frontmatter_or_raise(content)
        except FrontmatterParseError:
            post = frontmatter.Post("", **{})
        category_raw = post.metadata.get("Category", "")
        category = clean_category(category_raw, specs)

        template_fields = None
        if template_dir and category in TEMPLATE_MAP:
            template_path = template_dir / TEMPLATE_MAP[category]
            if template_path.exists():
                template_fields = get_template_fields(template_path)
                if verbose:
                    typer.echo(f"   ℹ️  Using template: {template_path.name}")

        result = validate_content(
            content,
            specs,
            no_llm=no_llm,
            verbose=verbose,
            template_fields=template_fields,
        )

        action_msg = ""
        if clean:
            allowed = get_allowed_fields(category, specs)
            if template_fields:
                allowed.update(template_fields)

            cleaned_metadata = clean_frontmatter(result.metadata, allowed)
            if len(cleaned_metadata) < len(result.metadata):
                removed = set(result.metadata.keys()) - set(cleaned_metadata.keys())
                action_msg = f"[bold yellow]CLEANED[/bold yellow] (removed: {', '.join(removed)})"
                if not dry_run:
                    post.metadata = cleaned_metadata
                    file.write_text(frontmatter.dumps(post), encoding="utf-8")
                    cleaned_count += 1
                else:
                    action_msg = f"[dry-run] Would remove: {', '.join(removed)}"
            else:
                action_msg = "No cleaning needed"

        status = "[green]PASS[/green]" if result.is_valid else "[red]FAIL[/red]"
        error_str = "\n".join(result.errors) if result.errors else ""
        suggestion_str = result.suggestion if result.suggestion else ""

        table.add_row(
            str(file.relative_to(path.parent if path.is_dir() else path.parent)),
            status,
            error_str,
            action_msg,
            suggestion_str,
        )

        if result.is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        results_json.append(
            {
                "file": str(file),
                "is_valid": result.is_valid,
                "errors": result.errors,
                "metadata": result.metadata,
            }
        )

    if json_output:
        print(json.dumps(results_json, indent=2))
        if invalid_count > 0 and not clean:
            raise typer.Exit(1)
        return

    console.print(table)
    summary = f"\nSummary: {valid_count} passed, {invalid_count} failed."
    if cleaned_count > 0:
        summary += f" {cleaned_count} files cleaned."
    typer.echo(summary)

    if invalid_count > 0 and not clean:
        raise typer.Exit(1)



if __name__ == "__main__":
    app()
