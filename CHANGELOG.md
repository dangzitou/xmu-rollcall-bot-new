# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- Direct monitor uses safe ``rc.get('rollcall_id')`` before building student_rollcalls URL so partial rollcall dicts no longer KeyError mid-notify
- Monitor start and direct monitor use safe account credential access with an early clear error on missing username/password
- ``handle_rollcalls`` uses defensive ``.get`` for display/type fields after extract normalisation
- ``get_notification_target`` resolves nested target fields via ``.get`` for partial hand-edited configs
- Direct monitor now checks notification helper exit code and timeouts instead of always logging success
- Wrap student_rollcalls fetches with retry_request (direct monitor + signed-count poll)
- CLI account-add profile fetch and session verification now use retry_request for transient network errors
- `extract_rollcalls` uses safe field access so partial API payloads no longer raise KeyError
- Number/radar delay helpers and manual-confirm gate use safe ``settings.get`` defaults
- CLI rollcall/notification config prompts use ``.get`` defaults so partial configs cannot KeyError mid-prompt

### Changed
- Expand docstrings on notification helper load/normalize/main entrypoints
- Annotate notification helper ``_temporary_env`` return type; document proxy Session patch
- Ongoing code quality improvements (type hints, docstrings, PEP8 spacing)
- Direct monitor uses shared BASE_URL/HEADERS for student_rollcalls instead of a hard-coded host
- CLI profile fetch uses shared BASE_URL/HEADERS instead of monitor module aliases
- Nested CLI config helpers and `utils.__getattr__` now declare return types
- Expand thin banner/footer/docstrings; annotate direct-monitor log cleanup return type
- Expand CLI command and nested-helper docstrings (config/start/refresh/switch and sub-actions)
