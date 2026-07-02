# Repo map and context packs

`cagent` builds a lightweight repo map to help the agent choose relevant files before reading full content.

## What the repo map contains

Each entry includes:

```text
path
language
line count
score
symbols
imports
```

The map is used by:

```bash
cagent run ...
cagent loop ...
```

and by the internal tools:

```text
repo_map
context_pack
```

## Python AST symbols

Python files are parsed with the standard-library `ast` module. This avoids a heavyweight parser dependency while giving better structure than regex alone.

Detected Python symbols include:

```text
class names
class methods
module-level functions
async functions
```

Class members are shown as qualified names:

```text
AccountService
AccountService.create_user
AccountService.refresh_user
background_refresh
```

## Python imports

Python imports are extracted from the AST as well:

```text
os
pathlib import Path
.models import User
```

## Fallback behavior

If a Python file cannot be parsed, cagent falls back to the older regex-based symbol and import scan. This keeps the repo map useful for incomplete or temporarily broken files.

## Query scoring

Query terms are matched against:

```text
path
symbols
imports
file text
```

Path matches receive the strongest boost, followed by symbol and import matches. Text matches are capped so one noisy file does not dominate every result.
