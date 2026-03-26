from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table

from local_first_common.cli import (
    dry_run_option,
    no_llm_option,
    verbose_option,
    resolve_dry_run,
)
from .logic import validate_content

app = typer.Typer(help="Content Frontmatter Validator")
console = Console()

@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="File or directory to validate")],
    dry_run: Annotated[bool, dry_run_option()] = False,
    no_llm: Annotated[bool, no_llm_option()] = False,
    verbose: Annotated[bool, verbose_option()] = False,
):
    """Validate Obsidian markdown frontmatter against Content Format Spec."""
    dry_run = resolve_dry_run(dry_run, no_llm)
    
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
    table.add_column("Suggestions", style="green")

    valid_count = 0
    invalid_count = 0

    for file in files:
        content = file.read_text(encoding="utf-8")
        is_valid, errors, suggestion = validate_content(content, no_llm=no_llm, verbose=verbose)
        
        status = "[green]PASS[/green]" if is_valid else "[red]FAIL[/red]"
        error_str = "\n".join(errors) if errors else ""
        suggestion_str = suggestion if suggestion else ""
        
        table.add_row(str(file.relative_to(path.parent if path.is_dir() else path.parent)), status, error_str, suggestion_str)
        
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

    console.print(table)
    typer.echo(f"\nSummary: {valid_count} passed, {invalid_count} failed.")

    if invalid_count > 0:
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
