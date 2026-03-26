# Content Frontmatter Validator (`frontmatter-validator`)

Validates Obsidian markdown frontmatter against the [Content Format Spec](https://jamalhansen.com/_strategy/Content%20Format%20Spec).

## Installation

```bash
uv tool install frontmatter-validator
```

## Usage

### Validate a single file
```bash
fm-validate validate path/to/post.md
```

### Validate a directory
```bash
fm-validate validate path/to/content/
```

### With template validation
Ensures the file is consistent with your Obsidian templates.

```bash
fm-validate validate path/to/post.md --template-dir ~/vaults/BrainSync/Templates
```

### Cleaning (removing unused fields)
Automatically remove frontmatter fields that are not in the spec or template.

```bash
fm-validate validate path/to/post.md --clean
```

### With LLM fuzzy suggestions
If validation fails, the tool can use an LLM to suggest fixes.

```bash
fm-validate validate path/to/post.md --verbose
```

## Configuration

The validation rules are defined in `specs.yaml`. You can customize:
- `universal` fields: required in every content type.
- `categories`: allowed fields per category (plus aliases like `[[Blog Post]]`).
- `validations`: conditional requirements (e.g., `published_date` required if `status` is `published`).

## Tech Stack

- **Python 3.12+**
- **PyYAML**: Spec configuration
- **python-frontmatter**: Metadata parsing
- **Typer**: CLI interface
- **local-first-common**: Run tracking and LLM providers
