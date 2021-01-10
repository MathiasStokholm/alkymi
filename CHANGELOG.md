# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Updated README.md with "Command Line Usage", "Upcoming Features" and "Known Issues" sections
- Included `labfile.py` in static type checking and linting
- Added a unit test for the built-in `file()` recipe generator

### Removed
- "clean" and "clean-cache" commands from Lab (these will be reimplemented properly at a later point)

### Changed
- Renamed alkymi's labfile from `lab.py` to `labfile.py` to fit the new "labfile" naming scheme

### Fixed
- Fixed type annotations in alkymi's labfile (`labfile.py`)
- Fixed reloading of recipe checksums from cache (these needed to be converted from lists to tuples due to JSON
serialization format). This would cause some recipes to be marked dirty even though they weren't.

## [0.0.3] - 2021-01-03
### Added
- Initial release

[Unreleased]: https://github.com/MathiasStokholm/alkymi/compare/v0.0.3...HEAD
[0.0.3]: https://github.com/MathiasStokholm/alkymi/releases/tag/v0.0.3
