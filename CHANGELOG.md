# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added a new `zip_results()` built-in recipe generator to zip together outputs from multiple recipes
- Documentation in the `docs/` directory. The documentation is built using Sphinx and hosted on
https://alkymi.readthedocs.io/en/latest/. The documentation can be built by running `python labfile.py brew docs`.

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

### Fixed
- Converted several captured variables inside tests to globals to avoid them interfering with hashing of the bound
functions
- Fixed an issue where a bound function changing between evaluations could cause the status to be reported as
"NotEvaluated" instead of "BoundFunctionChanged". Added a test step to check this.
- Fixed `utils.call()` to work regardless of operating system and added a small unit test
- Fixed caching of dictionaries output by ForeachRecipe
- Dictionaries are now serialized using a dict with key and value entries supporting arbitrary nesting, instead of being
pickled

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

[Unreleased]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.4...HEAD
[0.0.4]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/MathiasStokholm/alkymi/releases/tag/v0.0.3
