# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-11-02

### Fixed
- **Configuration File Loading**: Fixed critical issue where configuration files (`docpilot.toml`) were not being read properly, causing the tool to ignore user settings and fall back to defaults
- **Error Message Clarity**: Improved error messages for missing LLM packages to show correct installation commands (e.g., `pip install docpilot[openai]` instead of misleading `pip install docpilot`)
- **Syntax Error Handling**: Added clean, user-friendly error messages for Python syntax errors instead of displaying overwhelming stack traces with internal details
- **Partial Documentation Support**: Fixed logic to properly handle files with partial documentation, now correctly generates docstrings only for elements that don't already have them
- **Overwrite Flag Behavior**: Clarified and improved the `--overwrite` flag behavior to make it more intuitive when working with partially documented files

### Added
- Better error handling and user-facing error messages
- Improved configuration loading with proper fallback behavior

### Changed
- Enhanced mock provider output quality with more descriptive placeholder docstrings based on code analysis
- Improved CLI error display to be more professional and less intimidating for new users

## [0.1.0] - 2025-10-30

### Added
- First public release
- Basic docstring generation
- README.md generation
- Coverage reporting
- Multi-style docstring support

[Unreleased]: https://github.com/0xV8/docpilot/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/0xV8/docpilot/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/0xV8/docpilot/releases/tag/v0.1.0
