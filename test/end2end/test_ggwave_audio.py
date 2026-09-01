# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end tests for the ggwave audio transformer plugin.

These feed **real ggwave audio** (synthesized with ``ggwave.encode`` and
converted to the listener's int16 PCM format) through ovoscope's in-process
listener pipeline, so the plugin's ``on_audio`` decode + resample path is
exercised exactly as it would be from a microphone.

Run:
    uv run pytest test/ -v
"""
import unittest
from typing import List, Tuple

from ovos_bus_client.message import Message
from ovoscope.listener import MiniListener, get_mini_listener

from ovos_audio_transformer_plugin_ggwave import GGWavePlugin
from test.end2end.ggwave_audio import encode_payload

PLUGIN_NAME = "ovos-audio-transformer-plugin-ggwave"


def _listener(sample_rate: int, enabled: bool = True) -> MiniListener:
    plugin = GGWavePlugin(
        config={"start_enabled": enabled, "sample_rate": sample_rate}
    )
    return get_mini_listener(plugin_instances={PLUGIN_NAME: plugin})


def _decode(payload: str, sample_rate: int = 16000,
            enabled: bool = True) -> List[Tuple[str, dict]]:
    """Feed real ggwave audio for *payload* and return emitted (type, data)."""
    listener = _listener(sample_rate, enabled=enabled)
    try:
        audio = encode_payload(payload, sample_rate=sample_rate)
        msgs = listener.feed_audio_stream(audio, chunk_size=2048)
        return [(m.msg_type, m.data) for m in msgs]
    finally:
        listener.shutdown()


class TestUtteranceDecode(unittest.TestCase):
    """UTT: opcode → recognizer_loop:utterance, across sample rates."""

    def test_utt_decodes_at_48k_passthrough(self):
        """Native 48kHz ggwave audio decodes with no resampling."""
        msgs = _decode("UTT:hello world", sample_rate=48000)
        utts = [d for t, d in msgs if t == "recognizer_loop:utterance"]
        self.assertTrue(utts, f"no utterance decoded; got {[t for t, _ in msgs]}")
        self.assertEqual(utts[0]["utterances"], ["hello world"])

    def test_utt_decodes_at_16k_with_resample(self):
        """16kHz int16 mic-format audio is resampled internally and decodes."""
        msgs = _decode("UTT:turn on the lights", sample_rate=16000)
        utts = [d for t, d in msgs if t == "recognizer_loop:utterance"]
        self.assertTrue(utts, f"no utterance decoded; got {[t for t, _ in msgs]}")
        self.assertEqual(utts[0]["utterances"], ["turn on the lights"])


class TestOpcodes(unittest.TestCase):
    """Each opcode maps decoded audio to the right bus action."""

    def test_speak(self):
        msgs = _decode("SPEAK:good morning")
        speaks = [d for t, d in msgs if t == "speak"]
        self.assertTrue(speaks)
        self.assertEqual(speaks[0]["utterance"], "good morning")

    def test_ghs_skill_install_normalizes_url(self):
        msgs = _decode("GHS:OpenVoiceOS/skill-hello-world")
        installs = [d for t, d in msgs if t == "ovos.skills.install"]
        self.assertTrue(installs)
        self.assertEqual(
            installs[0]["url"],
            "https://github.com/OpenVoiceOS/skill-hello-world",
        )

    def test_pip_install(self):
        msgs = _decode("PIP:ovos-solver-plugin-foo")
        pips = [d for t, d in msgs if t == "ovos.pip.install"]
        self.assertTrue(pips)
        self.assertEqual(pips[0]["packages"], ["ovos-solver-plugin-foo"])

    def test_pip_uninstall(self):
        msgs = _decode("RMPIP:ovos-solver-plugin-foo")
        rmpips = [d for t, d in msgs if t == "ovos.pip.uninstall"]
        self.assertTrue(rmpips)
        self.assertEqual(rmpips[0]["packages"], ["ovos-solver-plugin-foo"])

    def test_bus_emits_raw_message(self):
        msgs = _decode("BUS:my.custom.event")
        self.assertIn("my.custom.event", [t for t, _ in msgs])


class TestGating(unittest.TestCase):
    """Payloads are ignored until the user enables the plugin."""

    def test_disabled_decodes_but_suppresses_action(self):
        """When not enabled the audio still decodes but no action fires."""
        msgs = _decode("UTT:hello world", sample_rate=16000, enabled=False)
        types = [t for t, _ in msgs]
        # the success acknowledgement still plays (something was decoded)...
        self.assertIn("mycroft.audio.play_sound", types)
        # ...but the gated action is suppressed
        self.assertNotIn("recognizer_loop:utterance", types)

    def test_invalid_payload_emits_no_action(self):
        """A non-opcode payload produces no action message."""
        msgs = _decode("NOTANOPCODE:whatever", sample_rate=16000)
        types = [t for t, _ in msgs]
        for forbidden in ("recognizer_loop:utterance", "speak",
                          "ovos.skills.install", "ovos.pip.install"):
            self.assertNotIn(forbidden, types)


class TestEnableDisable(unittest.TestCase):
    """The enable/disable bus handshake with the companion skill."""

    def test_enable_emits_enabled(self):
        listener = _listener(16000, enabled=False)
        try:
            listener._messages.clear()
            listener.bus.emit(Message("ovos.ggwave.enable"))
            types = [m.msg_type for m in listener._messages]
            self.assertIn("ovos.ggwave.enabled", types)
        finally:
            listener.shutdown()

    def test_disable_emits_disabled(self):
        listener = _listener(16000, enabled=True)
        try:
            listener._messages.clear()
            listener.bus.emit(Message("ovos.ggwave.disable"))
            types = [m.msg_type for m in listener._messages]
            self.assertIn("ovos.ggwave.disabled", types)
        finally:
            listener.shutdown()

    def test_enable_then_decode_unblocks_actions(self):
        """After an enable message a previously-gated payload is honoured."""
        listener = _listener(16000, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable"))
            audio = encode_payload("UTT:lights off", sample_rate=16000)
            msgs = listener.feed_audio_stream(audio, chunk_size=2048)
            utts = [m.data for m in msgs
                    if m.msg_type == "recognizer_loop:utterance"]
            self.assertTrue(utts)
            self.assertEqual(utts[0]["utterances"], ["lights off"])
        finally:
            listener.shutdown()


if __name__ == "__main__":
    unittest.main()
