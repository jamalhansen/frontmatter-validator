import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import frontmatter
import typer
from local_first_common.cli import (
    dry_run_option,
    init_config_option,
    json_option,
    no_llm_option,
    pipe_option,
    verbose_option,
)
from local_first_common.logging import setup_logging
from rich.console import Console
from rich.table import Table

from .core import (
    FrontmatterParseError,
    SpecLoadError,
    clean_category,
    clean_frontmatter,
    compute_default_fills,
    get_allowed_fields,
    get_template_fields,
    load_specs,
    parse_frontmatter_or_raise,
    validate_content,
)

TOOL_NAME = "frontmatter-validator"
DEFAULTS = {"provider": "ollama", "model": "llama3.2:3b"}

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
        Path | None,
        typer.Argument(help="File or directory to validate (or '-' for stdin)"),
    ] = None,
    spec: Annotated[
        Path | None, typer.Option("--spec", help="Path to custom validation spec YAML")
    ] = Path("specs.yaml"),
    template_dir: Annotated[
        Path | None, typer.Option("--template-dir", help="Path to Obsidian templates directory")
    ] = None,
    clean: bool = typer.Option(
        False, "--clean", help="Remove unused frontmatter fields NOT in spec"
    ),
    fill_defaults: bool = typer.Option(
        False,
        "--fill-defaults",
        help="Fill missing 'created' from the filename's date prefix, or the "
        "file's own mtime if there's no prefix. tags are handled by the real "
        "obsidian-vault-auto-tagger tool instead; canonical_url-from-slug is "
        "computed but not yet wired to write (a derived guess, needs its own "
        "confirmed rollout). category/status are never touched -- judgment calls.",
    ),
    pipe: Annotated[bool, pipe_option()] = False,
    json_output: Annotated[bool, json_option()] = False,
    dry_run: Annotated[bool, dry_run_option()] = False,
    no_llm: Annotated[bool, no_llm_option()] = False,
    verbose: Annotated[bool, verbose_option()] = False,
    init_config: Annotated[bool, init_config_option(TOOL_NAME, DEFAULTS)] = False,
):
    """Validate Obsidian markdown frontmatter against Content Format Spec."""
    # Deliberately NOT resolve_dry_run(dry_run, no_llm): this tool's write
    # actions (--clean, --fill-defaults) are fully deterministic, not
    # LLM-derived -- dry_run only gates them, and no_llm only controls
    # whether validate_content() generates a suggestion. The shared "no_llm
    # implies dry_run" rule exists to stop tools from writing fake/mocked
    # LLM output for real; it doesn't apply here, and silently defeated a
    # real --fill-defaults run: --no-llm was passed (correctly, to skip
    # suggestion generation) but nothing was written because of this.

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
            post = frontmatter.Post("")
        category_raw = post.metadata.get("category", "")
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
                    default=str,
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
    filled_count = 0
    results_json = []

    for file in files:
        content = file.read_text(encoding="utf-8")

        # Determine category for template lookup
        try:
            post = parse_frontmatter_or_raise(content)
        except FrontmatterParseError:
            post = frontmatter.Post("")
        category_raw = post.metadata.get("category", "")
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

        action_msgs = []
        pending_metadata = dict(result.metadata)
        needs_write = False

        if clean:
            allowed = get_allowed_fields(category, specs)
            if template_fields:
                allowed.update(template_fields)

            cleaned_metadata = clean_frontmatter(pending_metadata, allowed)
            if len(cleaned_metadata) < len(pending_metadata):
                removed = set(pending_metadata.keys()) - set(cleaned_metadata.keys())
                pending_metadata = cleaned_metadata
                if dry_run:
                    action_msgs.append(f"[dry-run] Would remove: {', '.join(removed)}")
                else:
                    action_msgs.append(f"[bold yellow]CLEANED[/bold yellow] (removed: {', '.join(removed)})")
                    needs_write = True
                    cleaned_count += 1
            else:
                action_msgs.append("No cleaning needed")

        if fill_defaults:
            fills = compute_default_fills(pending_metadata, file)
            # Scoped to 'created' for now -- tags are handled by the real
            # obsidian-vault-auto-tagger tool, and canonical_url is a derived
            # guess that needs its own visible-confirmation rollout before
            # this writes it unattended.
            created_fill = fills.get("created")
            if created_fill:
                value, reason = created_fill
                pending_metadata["created"] = value
                if dry_run:
                    action_msgs.append(f"[dry-run] Would fill created={value} ({reason})")
                else:
                    action_msgs.append(f"[bold cyan]FILLED[/bold cyan] created={value} ({reason})")
                    needs_write = True
                    filled_count += 1
            skipped = {k: v for k, v in fills.items() if k != "created"}
            if skipped:
                skipped_str = ", ".join(f"{k}={v[0]}" for k, v in skipped.items())
                action_msgs.append(f"[dim]Not filled (not yet wired): {skipped_str}[/dim]")

        if needs_write:
            post.metadata = pending_metadata
            file.write_text(frontmatter.dumps(post), encoding="utf-8")

        action_msg = "\n".join(action_msgs)

        status = "[green]PASS[/green]" if result.is_valid else "[red]FAIL[/red]"
        error_str = "\n".join(result.errors) if result.errors else ""
        suggestion_str = result.suggestion if result.suggestion else ""

        table.add_row(
            str(file.relative_to(path if path.is_dir() else path.parent)),
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
        print(json.dumps(results_json, indent=2, default=str))
        if invalid_count > 0 and not clean and not fill_defaults:
            raise typer.Exit(1)
        return

    console.print(table)
    summary = f"\nSummary: {valid_count} passed, {invalid_count} failed."
    if cleaned_count > 0:
        summary += f" {cleaned_count} files cleaned."
    if filled_count > 0:
        summary += f" {filled_count} files filled."
    typer.echo(summary)

    if invalid_count > 0 and not clean and not fill_defaults:
        raise typer.Exit(1)



if __name__ == "__main__":
    app()
