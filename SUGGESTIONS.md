# SUGGESTIONS — ovos-audio-transformer-plugin-ggwave

## SUG-001 — Move ggwave decoding into `on_audio()`, drop the pyaudio thread

`monitor_thread` (`__init__.py:193`) opens its own PyAudio stream at 48 kHz independently of
the OVOS audio pipeline. The `on_audio` hook (`__init__.py:185`) already receives audio chunks
from the listener — moving ggwave decoding there would:
- Remove the `pyaudio` dependency entirely
- Prevent duplicate microphone access conflicts
- Make audio processing observable and testable via the transformer chain

The existing TODO comment at `__init__.py:188` documents this intention.

## SUG-002 — Replace bare `except: pass` with explicit exception logging

`monitor_thread` (`__init__.py:224`) silently swallows all exceptions during payload
decode/dispatch. Change to:

```python
except Exception:
    LOG.exception("ggwave payload dispatch failed")
```

This is a two-line fix with zero risk and significant debuggability improvement.

## SUG-003 — Fix deprecated `Message` import

`__init__.py:9`: `from ovos_utils.messagebus import Message` triggers a DeprecationWarning.
Change to: `from ovos_bus_client.message import Message`.

## SUG-004 — Make individual opcodes configurable

All 11 opcodes are always registered. A config key like `disabled_opcodes: [BUS, JSON]` would
let operators restrict which operations are available over-the-air, reducing the attack surface
of the plugin.

## SUG-005 — Add missing gh-automations CI/CD workflows

Add standard workflows from `OpenVoiceOS/gh-automations@dev`:
`build-tests.yml`, `lint.yml`, `license-check.yml`, `pip-audit.yml`,
`publish-alpha.yml`, `publish-stable.yml`, `python-support.yml`, `repo-health.yml`.
Fix existing `unit_tests.yml` Python matrix (remove 3.7–3.9, 3.14; add 3.10–3.12).
