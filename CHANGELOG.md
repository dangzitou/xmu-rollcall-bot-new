# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- Direct monitor now checks notification helper exit code and timeouts instead of always logging success
- Wrap student_rollcalls fetches with retry_request (direct monitor + signed-count poll)
- CLI account-add profile fetch and session verification now use retry_request for transient network errors
- `extract_rollcalls` uses safe field access so partial API payloads no longer raise KeyError
- Number/radar delay helpers and manual-confirm gate use safe ``settings.get`` defaults

### Changed
- Ongoing code quality improvements (type hints, docstrings, PEP8 spacing)
- Direct monitor uses shared BASE_URL/HEADERS for student_rollcalls instead of a hard-coded host
- CLI profile fetch uses shared BASE_URL/HEADERS instead of monitor module aliases
- Nested CLI config helpers and `utils.__getattr__` now declare return types
- Expand thin banner/footer/docstrings; annotate direct-monitor log cleanup return type
