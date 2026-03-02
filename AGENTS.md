# alkymi – Repository Guide for AI Agents

## Overview

Alkymi is a pure Python (3.8+) library for describing and executing data processing pipelines with built-in caching
and conditional evaluation based on checksums. It allows users to write pipelines as decorated Python functions that
are automatically cached to disk. On subsequent runs, only the parts of the pipeline whose inputs have changed are
re-executed.

Key properties of the project:
- **No DSL** – pipelines are plain Python functions, so they work with linters, type checkers, and IDEs.
- **Automatic caching** – return values are serialized to disk regardless of type (supports numpy, pandas, arbitrary
  pickled objects, and plain JSON-serializable types).
- **Dirty-checking** – each recipe tracks checksums of its inputs and the hash of its own function body. A recipe is
  re-run only when something it depends on has changed.
- **CLI generation** – the `Lab` type turns a set of recipes into a Makefile-like command-line tool.
- **Cross-platform** – tested on Linux, Windows, and macOS.

---

## Repository Layout

```
alkymi/                     # Main library source package
  __init__.py               # Public API (re-exports recipe, foreach, Lab, recipes, utils, config)
  core.py                   # Graph construction and status computation engine
  recipe.py                 # Recipe[R] – the core building block
  foreach_recipe.py         # ForeachRecipe[R] – maps a function over a list/dict
  decorators.py             # @alk.recipe() and @alk.foreach() decorators
  lab.py                    # Lab – generates a CLI from a set of recipes
  recipes.py                # Built-in recipes: glob_files, file, arg, zip_results
  checksums.py              # Checksum computation (xxhash or MD5 fallback)
  serialization.py          # Disk serialization and deserialization of cached outputs
  config.py                 # AlkymiConfig singleton (global settings)
  types.py                  # Enums: Status, ProgressType, EvaluateProgress, CacheType, …
  utils.py                  # Helper: call() for subprocesses, run_on_thread()
  logging.py                # Logging helpers
  progress.py               # Rich-based progress visualization
  version.py                # __version__ string

tests/                      # pytest unit tests (one file per module)
  test_core.py
  test_caching.py
  test_serialization.py
  test_graph.py
  test_hashing.py
  test_foreach.py
  test_lab.py
  test_builtin_recipes.py
  test_utils.py

docs/                       # Sphinx documentation source
  source/
    getting_started/        # Installation, quickstart
    examples/               # MNIST, CLI, notebook
    advanced/               # Caching, checksums, sequences, configuration, execution
    api/                    # Auto-generated API reference

examples/                   # Standalone runnable examples
  mnist/                    # End-to-end MNIST dataset pipeline
  cli/                      # Command-line interface example
  notebook/                 # Jupyter notebook example

labfile.py                  # Alkymi's own build/test/lint recipes (self-hosting)
pyproject.toml              # Package metadata, dependencies, and dev dependency groups
requirements.txt            # Runtime dependencies: networkx, rich, markdown-it-py
mypy.ini                    # Mypy configuration
```

---

## Core Concepts

### Recipe

A `Recipe[R]` wraps a Python function and represents one step in a pipeline.

```python
import alkymi as alk

@alk.recipe()
def compute() -> int:
    return 42

result = compute.brew()   # executes, caches, returns 42
result = compute.brew()   # returns 42 from cache (no recomputation)
```

Important attributes:
- `ingredients` – upstream `Recipe` objects whose outputs are passed as arguments.
- `transient` – if `True`, the recipe is never cached and always re-run.
- `cache` – `CacheType.Cache`, `CacheType.NoCache`, or `CacheType.Auto`.

### ForeachRecipe

`ForeachRecipe[R]` applies a function to each element of a list or dict, caching results per element so that only
changed items are recomputed.

```python
@alk.foreach(list_recipe)
def process(item: str) -> str:
    return item.upper()
```

### Lab

`Lab` registers recipes and exposes them as a CLI tool, similar to a Makefile.

```python
lab = alk.Lab("my_project")
lab.add_recipes(recipe_a, recipe_b)
lab.open()   # parses sys.argv, e.g. `python labfile.py brew recipe_a`
```

### Status / Dirty-checking

Before executing, alkymi builds a DAG of all recipes and computes the `Status` of each node:

| Status | Meaning |
|--------|---------|
| `Ok` | Cached result is up-to-date |
| `NotEvaluatedYet` | No cached result exists |
| `IngredientDirty` | An upstream recipe needs recomputation |
| `InputsChanged` | Input checksums differ from the cached run |
| `BoundFunctionChanged` | The function's source code has changed |
| `OutputsInvalid` | The cached output is missing or corrupted |
| `CustomDirty` | A user-supplied cleanliness function returned `False` |

### Caching and Serialization

Outputs are stored under `.alkymi_cache/{module_name}/{recipe_name}/cache.json`.

Serialization tokens embedded in the JSON indicate how a value was stored:
- Plain JSON types are stored inline.
- `!#path#!` – a `pathlib.Path`.
- `!#ndarray#!` – a numpy array stored as a `.npy` file next to `cache.json`.
- `!#pickle#!` – an arbitrary Python object stored as a `.pkl` file.

---

## Key Classes and Relationships

```
AlkymiConfig (singleton)
  └─ global settings: cache, cache_path, allow_pickling, file_checksum_method, progress_type

Recipe[R]
  ├─ _func          – the bound Python function
  ├─ _ingredients   – List[Recipe], upstream dependencies
  ├─ _outputs       – cached in-memory result (Optional)
  ├─ _input_checksums – checksums used for the last evaluation
  └─ brew()         – triggers graph evaluation via core.py

ForeachRecipe[R] (extends Recipe[R])
  ├─ _mapped_inputs – the recipe providing the list/dict to iterate over
  └─ _mapped_outputs – per-element cached results

Lab
  ├─ _recipes       – Dict[str, Recipe] of registered recipes
  └─ open()         – CLI entry point

core.py (module-level functions)
  ├─ create_graph(recipe) → networkx.DiGraph
  └─ compute_recipe_status(recipe, graph) → Dict[Recipe, Status]
```

---

## How to Build, Lint, Test, and Type-Check

All developer tasks are defined as alkymi recipes in `labfile.py`. Run them with:

```shell
# Run the full unit test suite
uv run python labfile.py brew test

# Run tests with code coverage (outputs coverage.xml + terminal report)
uv run python labfile.py brew coverage

# Lint all source, example, and test files with flake8 (max line length 120)
uv run python labfile.py brew lint

# Type-check all files with mypy
uv run python labfile.py brew type_check

# Build Sphinx HTML documentation into docs/build/
uv run python labfile.py brew docs

# Build source and wheel distributions into dist/
uv run python labfile.py brew build
```

You can also run pytest directly:

```shell
pytest tests/
pytest tests/test_caching.py -v
```

Configuration files:
- `mypy.ini` – mypy settings (strict mode is not enabled by default).
- `pyproject.toml` – install all dev tools with `uv sync --dev`.

---

## Making Changes

### Adding a new recipe feature

1. Edit `alkymi/recipe.py` (or `alkymi/foreach_recipe.py` for foreach-specific changes).
2. If the feature affects the public API, export it from `alkymi/__init__.py`.
3. Add or update tests in `tests/test_core.py` or `tests/test_caching.py`.
4. Run `python3 labfile.py brew test` to verify.

### Adding a new built-in recipe

1. Add the factory function to `alkymi/recipes.py`.
2. Import and expose it via `alkymi/__init__.py` if needed.
3. Add tests in `tests/test_builtin_recipes.py`.

### Adding a new serialization type

1. Implement a serializer in `alkymi/serialization.py` following the existing pattern
   (`_serialize_*` / `_deserialize_*` helpers and a new token string).
2. Register the serializer in `_serialize` / `_deserialize`.
3. Add tests in `tests/test_serialization.py`.

### Changing checksum behavior

1. Edit `alkymi/checksums.py`.
2. Add tests in `tests/test_hashing.py`.

### Modifying the CLI (`Lab`)

1. Edit `alkymi/lab.py`.
2. Add tests in `tests/test_lab.py`.

---

## Runtime Dependencies

| Package | Minimum version | Purpose |
|---------|----------------|---------|
| `networkx` | 2.0 | DAG construction and topological ordering |
| `rich` | 10.7 | Fancy terminal progress bars |
| `markdown-it-py` | – | Docstring rendering in CLI help text |

Optional (automatically detected at runtime):
- `xxhash` ≥ 2.0.0 – faster checksums (falls back to MD5 when absent).
- `numpy` – enables specialized `.npy` serialization.
- `pandas` – enables pickle-based DataFrame serialization.

---

## Changelog

The project keeps a `CHANGELOG.md` in the repository root. It follows the
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Every change made to the repository must be recorded in `CHANGELOG.md`.**
Add your entries under the `## [Unreleased]` section at the top of the file,
grouped under one of: `Added`, `Changed`, `Fixed`, or `Removed`.

When a new version is released the `[Unreleased]` block is renamed to
`[X.Y.Z] - YYYY-MM-DD` and a fresh empty `[Unreleased]` block is added above
it.

---

## CI / Continuous Integration

GitHub Actions workflows live in `.github/workflows/`. The `build` workflow triggers on pushes and pull requests to
`master` and `develop`. It runs a matrix of Python 3.8–3.11 on Ubuntu, macOS, and Windows and executes:

1. `python labfile.py brew --progress=none lint`
2. `python labfile.py brew --progress=none coverage`
3. `python labfile.py brew --progress=none type_check`

Coverage results are uploaded to Codecov after every run.

---

## Project Metadata

| Field | Value |
|-------|-------|
| License | MIT (`LICENSE.md`) |
| Author | Mathias Bøgh Stokholm |
| PyPI package | `alkymi` |
| Documentation | https://alkymi.readthedocs.io/ |
| Python versions | 3.8, 3.9, 3.10, 3.11+ |
| Development status | Beta (latest: see `alkymi/version.py`) |
