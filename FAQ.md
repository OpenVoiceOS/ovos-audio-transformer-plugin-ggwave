# FAQ — ovos-audio-transformer-plugin-ggwave

## What is this plugin?

An OVOS `AudioTransformer` that decodes [ggwave](https://github.com/ggerganov/ggwave) audio
payloads from the microphone in real-time and dispatches them as OVOS MessageBus events.

## How does ggwave work?

ggwave encodes binary data as audible tones (audio QR codes). A sender device plays the tones;
this plugin records them via PyAudio and decodes them with the ggwave C library. No network
connection is required between sender and receiver.

## What opcodes does the plugin support?

| Opcode | Example | Action |
|---|---|---|
| `UTT:` | `UTT:turn off the lights` | Inject utterance into OVOS |
| `SPEAK:` | `SPEAK:hello world` | Speak text via TTS |
| `BUS:` | `BUS:mycroft.stop` | Emit arbitrary bus message |
| `JSON:` | `JSON:{...}` | Deserialize and emit a full Message |
| `SSID:` | `SSID:MyNetwork` | Store Wi-Fi SSID |
| `PSWD:` | `PSWD:secret` | Connect to Wi-Fi using stored SSID |
| `GHS:` | `GHS:OpenVoiceOS/ovos-skill-hello-world` | Install a GitHub skill |
| `PIP:` | `PIP:ovos-tts-plugin-piper` | Install a PyPI package globally |
| `RMPIP:` | `RMPIP:ovos-tts-plugin-piper` | Uninstall a PyPI package globally |
| `SPIP:` | `SPIP:ovos_audio:ovos-tts-plugin-piper` | Install into a specific service container |
| `RMSPIP:` | `RMSPIP:ovos_audio:ovos-tts-plugin-piper` | Uninstall from a specific service container |

## How do I enable the plugin?

By default, `user_enabled = False` (`__init__.py:37`). Either:
- Set `start_enabled: true` in the plugin config to enable on startup, **or**
- Use the companion `ovos-skill-ggwave` to enable/disable via voice commands.

## What is the `SPIP:` / `RMSPIP:` format?

`SPIP:<service_name>:<package>` — installs a package into a specific OVOS service container
(`handle_service_pip` — `__init__.py:80`). The service name must match the OPM service key
(e.g. `ovos_audio`, `ovos_core`). The plugin emits `ovos.pip.install.<service_name>`.

## What happens when `user_enabled` is False?

Decoded payloads are logged and silently discarded (`monitor_thread` — `__init__.py:213`).
No bus messages are emitted regardless of opcode.

## Why does Wi-Fi pairing use two separate payloads?

ggwave payloads are length-limited. Splitting SSID and password into two sequential transmissions
keeps each payload short. The plugin caches the SSID in `self._ssid` (`__init__.py:36`)
after receiving `SSID:`, then uses it when `PSWD:` arrives.

## What happens if `PSWD:` arrives before `SSID:`?

The plugin logs an error and emits `mycroft.audio.play_sound` with the configured error sound
(`handle_wifi_pswd` — `__init__.py:169`). No connection attempt is made.

## What sample rate and buffer size does the monitor thread use?

48,000 Hz, 1024 frames per buffer (`monitor_thread` — `__init__.py:196`). This matches
ggwave's expected input format.

## Can I use the plugin without PyAudio (e.g., in CI)?

Yes — mock `ggwave` and `pyaudio` in `sys.modules` before importing the plugin. The unit tests
(`test/unittests/test_plugin.py`) demonstrate this pattern.

## How do I run the tests?

```bash
uv run pytest test/unittests/ -v --cov=ovos_audio_transformer_plugin_ggwave --cov-report=term-missing
```

No audio hardware required — native modules are stubbed automatically.

## How do I run the plugin standalone (CLI)?

```bash
uv run python -m ovos_audio_transformer_plugin_ggwave
# or via the entry point:
uv run ggwave-cli
```

`launch_cli` (`__init__.py:239`) sets `start_enabled=True` and connects to the running OVOS bus.

## What is the plugin entry-point group?

`opm.plugin.audio_transformer` (see `setup.py` / `entry_points.txt`).
