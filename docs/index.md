# ovos-audio-transformer-plugin-ggwave

An OVOS `AudioTransformer` plugin that listens for [ggwave](https://github.com/ggerganov/ggwave)
audio-encoded payloads via a dedicated microphone thread and dispatches them as OVOS bus events.

ggwave encodes binary data as audible tones ("audio QR codes"). This plugin decodes those tones
in real-time and maps them to OVOS actions via a prefix-based opcode protocol.

## Architecture

```
Microphone (PyAudio, 48 kHz, 1024-frame chunks)
     │
     ▼
monitor_thread  ──► ggwave.decode()
     │
     ├─ decoded payload ──► opcode dispatcher (self.OPCODES)
     │                            │
     │         ┌──────────────────┼──────────────────┐
     │         ▼                  ▼                  ▼
     │     UTT: → bus         SPEAK: → bus       BUS: → bus
     │     SSID:/PSWD:        GHS:/PIP:          JSON: → bus
     │     SPIP:/RMSPIP:      RMPIP:
     │
     └─ user_enabled gate: payloads ignored when False
```

## Key Classes

| Class | File | Description |
|---|---|---|
| `GGWavePlugin` | `ovos_audio_transformer_plugin_ggwave/__init__.py:12` | Main plugin; extends `AudioTransformer` |

## Opcode Reference

| Opcode prefix | Handler | Bus message emitted |
|---|---|---|
| `UTT:` | `handle_utt` — `:141` | `recognizer_loop:utterance` |
| `SPEAK:` | `handle_speak` — `:153` | `speak` |
| `BUS:` | `handle_bus` — `:137` | *(arbitrary msg_type from payload)* |
| `JSON:` | `handle_json` — `:157` | *(deserialized Message from payload)* |
| `SSID:` | `handle_wifi_ssid` — `:146` | *(stores SSID for next PSWD:)* |
| `PSWD:` | `handle_wifi_pswd` — `:167` | `ovos.phal.nm.connect` or `.open.network` |
| `GHS:` | `handle_skill` — `:64` | `ovos.skills.install` |
| `PIP:` | `handle_pip` — `:70` | `ovos.pip.install` |
| `RMPIP:` | `handle_remove_pip` — `:75` | `ovos.pip.uninstall` |
| `SPIP:` | `handle_service_pip` — `:80` | `ovos.pip.install.<service>` |
| `RMSPIP:` | `handle_service_remove_pip` — `:107` | `ovos.pip.uninstall.<service>` |

## Bus Events (inbound)

| Message type | Handler | Effect |
|---|---|---|
| `ovos.ggwave.enable` | `handle_enable` — `:50` | Sets `user_enabled = True`, emits `ovos.ggwave.enabled` |
| `ovos.ggwave.disable` | `handle_disable` — `:57` | Sets `user_enabled = False`, emits `ovos.ggwave.disabled` |

The voice interface (skill `ovos-skill-ggwave`) emits `ovos.ggwave.enable/disable` in response
to user voice commands, and listens for `ovos.ggwave.enabled/disabled` to update its own state.

## Configuration

| Key | Default | Description |
|---|---|---|
| `start_enabled` | `False` | If `True`, the plugin accepts payloads immediately without a voice command |

## Enable/Disable Gate

All opcode handlers are gated by `GGWavePlugin.user_enabled`
(`__init__.py:213`). When `False`, decoded payloads are logged and discarded.

## Wi-Fi Pairing Protocol

Two-step sequence using `SSID:` then `PSWD:`:
1. `SSID:MyNetwork` → stores SSID in `self._ssid`
2. `PSWD:s3cr3t` → emits `ovos.phal.nm.connect` with SSID + password
3. `PSWD:` (empty) → emits `ovos.phal.nm.connect.open.network` (open network)

Receiving `PSWD:` without a prior `SSID:` is an error — emits an error sound.

## Testing

```bash
uv run pytest test/unittests/ -v --cov=ovos_audio_transformer_plugin_ggwave --cov-report=term-missing
```

Tests mock `ggwave` and `pyaudio` via `sys.modules` stubs — no audio hardware required.

## Related

- [ggwave C library](https://github.com/ggerganov/ggwave)
- [ovos-skill-ggwave](https://github.com/OpenVoiceOS/ovos-skill-ggwave) — voice interface
- [ovos-plugin-manager AudioTransformer](https://github.com/OpenVoiceOS/ovos-plugin-manager)
