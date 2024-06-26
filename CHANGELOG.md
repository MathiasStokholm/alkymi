# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]


## [0.3.1] - 2024-05-16
### Fixed
- Fixed readthedocs.org documentation build now requiring a .readthedocs.yaml config file
- Fixed a bug where the actual error message from an exception happening during execution through a `Lab` instance would
be omitted
- Fixed an issue where exceptions in recipes could cause asyncio to print warning information about the `_schedule`
coroutine never being awaited
- Fixed an issue where asyncio would warn about exceptions not having been retrieved from futures when more than one
exception was raised during parallel execution. Alkymi will now just raise the first exception it encounters. 


## [0.3.0] - 2024-04-23
### Added
- Added a new `doc` property to recipes that provides a documentation string for the recipe. If not provided upon
creation of a recipe, alkymi will try to infer the documentation string by parsing the bound function's docstring
- Added a new optional `doc` argument to the `arg` recipe that provides a documentation string for the argument

### Changed
- `stderr` is now streamed by default when using the `utils.call()` utility function [#42](https://github.com/MathiasStokholm/alkymi/issues/42)
- When utilizing the `Lab` command line interface, alkymi will now omit alkymi internals from tracebacks resulting from
exceptions raised by user code (recipes) 
- Refactored the `Lab` command line interface to provide rich information by making use of the new `doc` property on
`Recipe` and `arg` instances
- Changed the allowed arguments to `brew X` to only contain arguments that affect recipe `X`

### Fixed
- Remove unnecessary decimal points in fancy progress output [#42](https://github.com/MathiasStokholm/alkymi/issues/42)
- Fixed a bug where the terminal cursor would disappear if an exception was thrown during execution
- Fixed a bug where the terminal cursor would disappear if a `Lab` call to `brew` was terminated using ctrl-c
- Fixed a bug where recipes returning `None` (no return value) would not be correctly cached on subsequent runs
- Fixed CI pipeline integration with codecov.io (test coverage)
- Fixed CI pipeline execution on MacOS agents

### Removed
- Removed the ability to brew multiple recipes from a `Lab` by listing them in succession


## [0.2.1] - 2023-04-27
### Fixed
- Fixed a bug where execution would crash if called from a thread that had an already running event loop [#39](https://github.com/MathiasStokholm/alkymi/issues/39)
- Fixed a bug where execution would crash by erroneously trying to cancel an `_asyncio.Task` instead of only unused
coroutines [#38](https://github.com/MathiasStokholm/alkymi/issues/38)


## [0.2.0] - 2023-04-10
### Added
- Added `rich` as a runtime dependency
- Added fancy progress output mode that shows a summary of the execution at the bottom of the console using [Rich](https://rich.readthedocs.io/).
- Added support for Python 3.11

### Changed
- Rewrote parallel execution to only run bound functions in parallel, but use asyncio for the main execution logic
- Bumped `mypy` version to `1.2.0` (only used for development)
- Bumped `coverage` version to `6.4.2` (only used for development)

### Fixed
- Fixed a bug where a deadlock could occur when evaluating a number of `ForeachRecipes` with the same number of jobs
- Fixed a bug where a certain graph configuration could prevent parallelization from happening correctly
- Fixed a regression where all cached recipe outputs would always be loaded during execution, regardless of whether they
were needed to produce the requested output.

### Removed
- Dropped support for Python 3.6


## [0.1.0] - 2023-03-07
### Added
- Added `networkx` as a runtime dependency
- Added support for parallel execution - the `brew()` function now takes a `jobs` parameter that controls
parallelization of the recipe evaluation.
- Added support for parallel execution to the `Lab` CLI - use `--jobs` or `-j` when calling `brew` to run pipeline in
parallel
- Added `twine` and `wheel` to `dev-requirements.txt`

### Changed
- Rewrote the internals of alkymi to create and use a `networkx` graph (DAG) for execution. This change will enable
future changes, like running recipes in parallel.
- Renamed `alkymi.py` to `core.py`
- Converted `ForeachRecipe` to have the same functional interface as a regular `Recipe`. This change enables the
functions in `core.py` to not have special handling for `ForeachRecipe`, which makes the code simpler and easier to
maintain.
- Coverage step `labfile.py brew coverage` will not print which lines lack test coverage
- The `invoke` and `invoke_foreach` functions have been moved from `recipe.py` and `foreach_recipe.py` into `core.py`
to allow more control over the execution flow.

### Removed
- Removed the special `MappedInputsDirty` status, which only applied to `ForeachRecipe`. If a `ForeachRecipe` has only
completed a partial evaluation of its enumerable input, its status will now show `InputsChanged` instead.

## [0.0.7] - 2022-12-02
### Added
- Added a `file_checksum_method` config option that can be used to select whether to use file content hashing (default)
or file modification timestamps for calculating the checksum of an external file represented by a `Path` object

### Fixed
- Fixed a bug where CLI arguments containing a hyphen would not be parsed correctly when used in a `Lab`
- Fixed a bug where the implementation of coverage in `labfile.py` would break the debugger for the entire script. Now
only the `coverage` steps breaks debugging (which is expected, since coverage replaces the tracing function used by the
debugger)

### Changed
- Made the `call()` utility function print program outputs (stdout) to stdout by default - this can be controlled using
the `echo_output_to_stream` argument.

## [0.0.6] - 2022-05-17
### Added
- Added py.typed file to signal to downstream user's that alkymi has type annotations
- Added optional dependency on xxhash to speed up hashing of large files (`Path` objects outside of alkymi's cache)
- Added option to supply ingredients to a recipe by using argument names that match recipes (ala pytest's fixtures)
- Added support for explicit naming of recipes (if not provided, the bound function name will be used)
- Added support for providing CLI arguments to recipes through a `Lab` using the new `register_arg()` function
- Added tests for the `Lab` class

### Changed
- Updated Sphinx and associated packages to fix documentation build errors
- Updated development libraries (pytest, coverage, sphinx, mypy, flake8)
- Made the `call()` utility function print error stack traces to stderr by default - this can be controlled using the
`echo_error_to_stream` argument.

### Fixed
- Fixed a bug where file names were not taken into account during checksumming (only file content was taken into
account)
- Fixed a bug where a recipe's cache path would be different when a script was invoked as a relative or absolute path
- Fixed a bug where item validity was not being taken into account in `ForeachRecipe` (e.g., an invalid Path such as a
deleted file would not cause reevaluation)
- Fixed a bug where a `ForeachRecipe` wouldn't be completely reevaluated if its bound function changed
- Fixed a bug where changing the default value of an argument to a bound function did not cause the checksum of the
bound function to change
- Fixed coverage to correctly include alkymi imports when executed through `labfile.py`

### Removed
- `kwargs`/`NamedArgs` built-in recipe removed (functionality can now be mimicked using the built-in `Arg`)
- Dropped support for Python 3.5

## [0.0.5] - 2021-03-17
### Added
- Added a new `zip_results()` built-in recipe generator to zip together outputs from multiple recipes
- Documentation in the `docs/` directory. The documentation is built using Sphinx and hosted on
https://alkymi.readthedocs.io/en/latest/. The documentation can be built by running `python labfile.py brew docs`.
- Added checksum unit tests for the `Path` type
- Added unit test for caching of recipes that do not return anything (None)
- Added `allow_pickling` configuration option to let the user turn off pickling for serialization, deserialization and
checksumming and a unit test for it
- Added test coverage using `coverage` and https://codecov.io (see the `coverage` recipe in `labfile.py`)

### Changed
- Regular checks for cleanliness are now run even if a custom cleanliness check passes (e.g. for the `glob_files()`
built-in recipe generator). This ensures that changes to external files and others are correctly caught and handled.
- Broke `Status.Dirty` into several more explicit causes of dirtiness (e.g. `OutputsInvalid`) to make it more clear to
the user why a given recipe has been marked dirty
- Moved functions for checking Recipe and ForeachRecipe dirtiness to alkymi.alkymi to reduce the complexity of the
classes
- Moved the core logic of the `Recipe.brew()` function to alkymi.alkymi
- Provide names explicitly to built-in recipe generators to avoid name clashes when a built-in recipe generator is used
multiple times in a single module
- Greatly simplified the serialization and deserialization logic and got rid of generators
- Converted the built-in recipe types `Args` and `NamedArgs` to be subclasses of `Recipe` to avoid the clunky `.recipe`
property.
- Updated `README.md` to reflect the new documentation page at https://alkymi.readthedocs.io/en/latest/.
- Replaced the usage of `tuple` with a new `Outputs` type that keeps most of the behavior, but ensures that all return
types are valid
- Made `Recipe` generic in the return type and forwarded return type information from decorators to allow `brew` to
return valid type information
- Updated built-in recipes to supply return type information to their `Recipe` objects
- Use the highest available protocol when pickling for serialization and checksumming

### Fixed
- Converted several captured variables inside tests to globals to avoid them interfering with hashing of the bound
functions
- Fixed an issue where a bound function changing between evaluations could cause the status to be reported as
"NotEvaluated" instead of "BoundFunctionChanged". Added a test step to check this.
- Fixed `utils.call()` to work regardless of operating system and added a small unit test
- Fixed caching of dictionaries output by ForeachRecipe
- Dictionaries are now serialized using a dict with key and value entries supporting arbitrary nesting, instead of being
pickled
- Fixed a bug where non-existent `Path` objects would result in the same checksum
- Fixed a bug where recipes without return values would remain `NotEvaluated` even though they had been evaluated and
cached

## [0.0.4] - 2021-02-05
### Added
- Updated README.md with "Command Line Usage", "Upcoming Features" and "Known Issues" sections
- Included `labfile.py` in static type checking and linting
- Added a unit test for the built-in `file()` recipe generator
- Made cache directory configurable using `AlkymiConfig` and added a test for it
- Added a new test to verify that partially executed ForeachRecipes can be reloaded from cache and continue from point
of interruption/failure

### Removed
- "clean" and "clean-cache" commands from Lab (these will be reimplemented properly at a later point)

### Changed
- Renamed alkymi's labfile from `lab.py` to `labfile.py` to fit the new "labfile" naming scheme
- ForeachRecipe now supports saving/restoring partial evaluation states to the cache. This fixes the issue where a
failure in one of the foreach evaluations could cause all the work to be lost
- Recipes will now be marked dirty if their bound function has changed between invocations
- ForeachRecipe now only serializes each output once
- Outputs are now loaded lazily from the cache. This means that actual deserialization is deferred until an output is
actually needed for computation.
- alkymi's labfile now uses `exit()` instead of raising exceptions in order to not clutter the output of tests etc.
- Adapted the way that external (outside alkymi's cache) files are checked for validity to see if they have changed
between alkymi evaluations
- Updated README.md to reflect recently merged features

### Fixed
- Fixed type annotations in alkymi's labfile (`labfile.py`)
- Fixed reloading of recipe checksums from cache (these needed to be converted from lists to tuples due to JSON
serialization format). This would cause some recipes to be marked dirty even though they weren't.
- Fixed a bug where the aggregate checksum for all mapped inputs to a ForeachRecipe weren't being saved and restored
from cache

## [0.0.3] - 2021-01-03
### Added
- Initial release

[Unreleased]: https://github.com/MathiasStokholm/alkymi/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/MathiasStokholm/alkymi/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/MathiasStokholm/alkymi/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/MathiasStokholm/alkymi/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/MathiasStokholm/alkymi/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.7...v0.1.0
[0.0.7]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.6...v0.0.7
[0.0.6]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/MathiasStokholm/alkymi/releases/tag/v0.0.3
