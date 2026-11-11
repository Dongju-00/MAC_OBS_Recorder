# Recorder Configuration Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan.

**Goal:** Let users save recording options in a JSON file and find customization instructions in an English README.

**Architecture:** An explicit `--config PATH` loads defaults for existing CLI options. Explicit CLI values override saved settings. Validate file keys, types, choices, and ranges before controlling Chrome or OBS. Do not auto-load files or save credentials.

**Tech Stack:** Python standard library, argparse, JSON, unittest.

## Constraints

- Keep existing defaults and commands working.
- Keep mode flags explicit; the configuration cannot start recording itself.
- Use existing option names with underscores as JSON keys.
- Keep passwords in the existing environment variable or interactive prompt.
- Keep capture/output settings in OBS.

## Review Focus

- Unknown keys and mode flags must fail with clear CLI errors.
- Booleans must not pass as numbers; nonfinite numbers must be rejected.
- Missing or malformed files must fail before external control.
- CLI overrides must include both fullscreen directions.
- Recorder-specific countdown defaults must remain unchanged.

## Implementation

- [x] Add tests for saved values, CLI overrides, invalid configuration, and unchanged defaults.
- [x] Run new tests and confirm failure because configuration is unsupported.
- [x] Extract argument parsing into `parse_args(argv=None)` and add validated JSON defaults.
- [x] Add `config.example.json`, ignore local `config.json`, and document copying and overrides.
- [x] Run the full Python and browser suites, README link/option checks, and `git diff --check`.

Review caught inconsistent option abbreviation between the preliminary and full parsers. A regression test reproduced silently ignored configuration; both parsers now reject abbreviations.

Validation: 41 Python tests passed, browser tests passed, 28 README links and 22 recorder CLI flags checked, and `git diff --check` passed. Actual OBS capture and audio were not exercised.
