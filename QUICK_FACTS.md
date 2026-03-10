# QUICK_FACTS — ovos-audio-transformer-plugin-ggwave

| Field | Value |
|---|---|
| **Package name** | `ovos-audio-transformer-plugin-ggwave` |
| **Python package** | `ovos_audio_transformer_plugin_ggwave` |
| **Entry point group** | `opm.plugin.audio_transformer` |
| **Main class** | `GGWavePlugin` — `ovos_audio_transformer_plugin_ggwave/__init__.py:12` |
| **Base class** | `AudioTransformer` (ovos-plugin-manager) |
| **Opcodes** | 11: UTT, SPEAK, BUS, JSON, SSID, PSWD, GHS, PIP, RMPIP, SPIP, RMSPIP |
| **Inbound bus msgs** | `ovos.ggwave.enable`, `ovos.ggwave.disable` |
| **Outbound bus msgs** | `ovos.ggwave.enabled`, `ovos.ggwave.disabled`, + per-opcode messages |
| **Audio input** | PyAudio, 48 kHz, 1024-frame chunks |
| **Config key** | `start_enabled` (bool, default `False`) |
| **CLI entry point** | `launch_cli` — `__init__.py:239` |
| **License** | Apache 2.0 |
| **Tests** | `test/unittests/test_plugin.py` (31 tests) |
| **Docs** | `docs/index.md` |
| **Voice interface** | `ovos-skill-ggwave` (separate repo) |
