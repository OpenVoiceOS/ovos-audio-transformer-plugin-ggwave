
# AUDIT — ovos-audio-transformer-plugin-ggwave

## Documentation Status (2026-03-10)
- [x] QUICK_FACTS.md
- [x] FAQ.md
- [x] MAINTENANCE_REPORT.md
- [x] AUDIT.md
- [x] SUGGESTIONS.md
- [x] docs/index.md
- [x] test/unittests/test_plugin.py (31 tests, all passing)

## Known Issues

### ISSUE-001 — `monitor_thread` uses `pyaudio` directly; blocks removal of hardware dependency
- **File**: `__init__.py:193–229`
- **Severity**: Medium
- The `on_audio` callback (`__init__.py:185`) is intentionally unused and contains a TODO to
  move ggwave decoding there. The pyaudio thread runs independently of the OVOS audio pipeline,
  duplicating microphone access and preventing the `pyaudio` dependency from being dropped.

### ISSUE-002 — Silent `except: pass` swallows all errors in `monitor_thread`
- **File**: `__init__.py:224`
- **Severity**: Medium
- A bare `except: pass` suppresses all exceptions during payload decode/dispatch, making
  errors invisible. Should at minimum be `except Exception: LOG.exception(...)`.

### ISSUE-003 — `ovos_utils.messagebus.Message` deprecated import
- **File**: `__init__.py:9`
- **Severity**: Low
- `from ovos_utils.messagebus import Message` triggers a DeprecationWarning.
  Should be `from ovos_bus_client.message import Message`.

### ISSUE-004 — CI matrix has invalid Python 3.14 and EOL 3.7–3.9
- **File**: `.github/workflows/unit_tests.yml`
- **Severity**: Low
- Python 3.14 does not exist; 3.7–3.9 are EOL. Matrix should be 3.10, 3.11, 3.12.

### ISSUE-005 — Missing standard gh-automations CI/CD workflows
- **File**: `.github/workflows/`
- **Severity**: Medium
- Missing: `build-tests.yml`, `lint.yml`, `license-check.yml`, `pip-audit.yml`,
  `publish-alpha.yml`, `publish-stable.yml`, `python-support.yml`, `repo-health.yml`.

### ISSUE-006 — `setup.py` not migrated to `pyproject.toml`
- **File**: `setup.py`
- **Severity**: Low

## Next Steps
- Fix silent `except: pass` → `except Exception: LOG.exception(...)` (ISSUE-002) — highest priority
- Fix deprecated `Message` import (ISSUE-003)
- Add missing gh-automations workflows (ISSUE-005)
- Move ggwave decoding into `on_audio()` and drop pyaudio thread (ISSUE-001)
- Fix CI Python matrix (ISSUE-004)
