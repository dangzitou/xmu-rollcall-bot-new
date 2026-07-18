# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- Direct monitor now checks notification helper exit code and timeouts instead of always logging success
- Wrap student_rollcalls fetches with retry_request (direct monitor + signed-count poll)

### Changed
- Ongoing code quality improvements (type hints, docstrings)
- Direct monitor uses shared BASE_URL/HEADERS for student_rollcalls instead of a hard-coded host
