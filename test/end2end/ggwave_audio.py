# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""Helpers to synthesize *real* ggwave audio for end-to-end tests.

``ggwave.encode`` returns a 48kHz float32 waveform. The OVOS listener feeds an
audio transformer int16 PCM at its configured sample rate (typically 16kHz), so
these helpers downsample/convert the genuine ggwave waveform to the format the
plugin will actually receive — the tests therefore exercise the same decode +
resample path as a real microphone capture, not a stub.
"""
from __future__ import annotations

import ggwave
import numpy as np

GGWAVE_RATE = 48000

# Audible protocols survive a trip through a 16kHz capture (Nyquist 8kHz);
# ultrasound protocols (>=3) do not, so the helper defaults to protocol 1.
AUDIBLE_NORMAL = 1


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return x.astype(np.float32)
    n_out = int(round(len(x) * dst / src))
    return np.interp(np.linspace(0, len(x) - 1, n_out),
                     np.arange(len(x)), x).astype(np.float32)


def encode_payload(payload: str,
                   sample_rate: int = 16000,
                   protocol_id: int = AUDIBLE_NORMAL,
                   volume: int = 20) -> bytes:
    """Return *payload* as real ggwave audio in listener format.

    Args:
        payload: opcode-prefixed string, e.g. ``"UTT:hello world"``.
        sample_rate: target rate of the returned int16 PCM (e.g. 16000 to
            simulate a 16kHz mic, or 48000 for a passthrough test).
        protocol_id: ggwave protocol; keep audible (0-2) for sub-48kHz rates.
        volume: ggwave transmit volume.

    Returns:
        int16 little-endian PCM bytes at *sample_rate*, mono.
    """
    waveform = ggwave.encode(payload, protocolId=protocol_id, volume=volume)
    f32_48k = np.frombuffer(waveform, dtype=np.float32)
    f32 = _resample(f32_48k, GGWAVE_RATE, sample_rate)
    return (np.clip(f32, -1.0, 1.0) * 32767).astype("<i2").tobytes()
