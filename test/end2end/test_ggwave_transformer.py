# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end tests for GGWavePlugin through AudioTransformersService.

These tests exercise the full listener pipeline:
  GGWavePlugin → AudioTransformersService → FakeBus → captured messages

The native ggwave C extension is mocked so tests run without audio hardware.
Plugin instances are injected directly into MiniListener to avoid relying on
OPM entry-point discovery in the test environment.

Test isolation note: ``ggwave.decode`` is patched via ``unittest.mock.patch``
for the duration of each test so that mutations do not leak into other test
modules that share the same ``sys.modules["ggwave"]`` stub.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub the native ggwave extension before any plugin code is imported.
# Use setdefault so that the first importer wins; then bind our local
# reference to whatever actually ends up in sys.modules.
# ---------------------------------------------------------------------------
_tmp_ggwave = types.ModuleType("ggwave")
_tmp_ggwave.init = MagicMock(return_value=MagicMock())
_tmp_ggwave.free = MagicMock()
_tmp_ggwave.decode = MagicMock(return_value=None)
sys.modules.setdefault("ggwave", _tmp_ggwave)

# Stub pyaudio (used by the deprecated launch_cli path only).
_tmp_pyaudio = types.ModuleType("pyaudio")
_tmp_pyaudio.PyAudio = MagicMock()
_tmp_pyaudio.paFloat32 = 1
sys.modules.setdefault("pyaudio", _tmp_pyaudio)

# Bind to whatever is actually in sys.modules (may differ from _tmp_ggwave
# if another test module registered the stub first).
import ggwave as _ggwave_mod  # noqa: E402

from ovos_bus_client.message import Message  # noqa: E402
from ovoscope.listener import get_mini_listener  # noqa: E402

PLUGIN_NAME = "ovos-audio-transformer-plugin-ggwave"
_AUDIO_CHUNK = b"\x00" * 1024


def _make_listener(start_enabled: bool = True) -> "MiniListener":
    """Helper: instantiate plugin and inject into MiniListener.

    Using plugin_instances bypasses OPM entry-point discovery so the test
    works even when the plugin is not registered under ``opm.plugin.audio_transformer``.
    """
    from ovos_audio_transformer_plugin_ggwave import GGWavePlugin

    with patch("ovos_utils.create_daemon"):
        plugin = GGWavePlugin(config={"start_enabled": start_enabled})
    return get_mini_listener(
        plugin_instances={PLUGIN_NAME: plugin},
    )


class TestGGWaveUttOpcode(unittest.TestCase):
    """UTT opcode injects utterance via AudioTransformersService."""

    def setUp(self) -> None:
        self._patcher = patch.object(_ggwave_mod, "decode",
                                     MagicMock(return_value=b"UTT:turn on the lights"))
        self._patcher.start()
        self.listener = _make_listener(start_enabled=True)

    def tearDown(self) -> None:
        self.listener.shutdown()
        self._patcher.stop()

    def test_utt_opcode_produces_recognizer_loop_utterance(self) -> None:
        """UTT payload → recognizer_loop:utterance is emitted through the pipeline."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        types_ = [m.msg_type for m in msgs]
        self.assertIn("recognizer_loop:utterance", types_)

    def test_utt_opcode_utterance_data_contains_text(self) -> None:
        """The utterance text from the UTT payload appears in message data."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        utt_msgs = [m for m in msgs if m.msg_type == "recognizer_loop:utterance"]
        self.assertTrue(len(utt_msgs) > 0)
        self.assertIn("turn on the lights", utt_msgs[0].data["utterances"])


class TestGGWaveSpeakOpcode(unittest.TestCase):
    """SPEAK opcode emits a speak message via AudioTransformersService."""

    def setUp(self) -> None:
        self._patcher = patch.object(_ggwave_mod, "decode",
                                     MagicMock(return_value=b"SPEAK:hello world"))
        self._patcher.start()
        self.listener = _make_listener(start_enabled=True)

    def tearDown(self) -> None:
        self.listener.shutdown()
        self._patcher.stop()

    def test_speak_opcode_emits_speak_message(self) -> None:
        """SPEAK payload → speak message is emitted through the pipeline."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        self.assertTrue(any(m.msg_type == "speak" for m in msgs))

    def test_speak_opcode_message_contains_text(self) -> None:
        """The speak message carries the correct utterance text."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        speak_msgs = [m for m in msgs if m.msg_type == "speak"]
        self.assertTrue(len(speak_msgs) > 0)
        self.assertEqual(speak_msgs[0].data.get("utterance"), "hello world")


class TestGGWaveBusOpcode(unittest.TestCase):
    """BUS opcode emits an arbitrary bus message via AudioTransformersService."""

    def setUp(self) -> None:
        self._patcher = patch.object(_ggwave_mod, "decode",
                                     MagicMock(return_value=b"BUS:my.custom.event"))
        self._patcher.start()
        self.listener = _make_listener(start_enabled=True)

    def tearDown(self) -> None:
        self.listener.shutdown()
        self._patcher.stop()

    def test_bus_opcode_emits_custom_message_type(self) -> None:
        """BUS payload → the specified message type is emitted on the bus."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        self.assertTrue(any(m.msg_type == "my.custom.event" for m in msgs))


class TestGGWaveDisabledPlugin(unittest.TestCase):
    """Disabled plugin silently ignores all payloads."""

    def setUp(self) -> None:
        self._patcher = patch.object(_ggwave_mod, "decode",
                                     MagicMock(return_value=b"UTT:ignored payload"))
        self._patcher.start()
        self.listener = _make_listener(start_enabled=False)

    def tearDown(self) -> None:
        self.listener.shutdown()
        self._patcher.stop()

    def test_disabled_plugin_suppresses_utterance(self) -> None:
        """With start_enabled=False the UTT payload is silently dropped."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        self.assertFalse(
            any(m.msg_type == "recognizer_loop:utterance" for m in msgs)
        )


class TestGGWaveNoDecodeResult(unittest.TestCase):
    """When ggwave.decode returns None, no bus messages are emitted."""

    def setUp(self) -> None:
        self._patcher = patch.object(_ggwave_mod, "decode",
                                     MagicMock(return_value=None))
        self._patcher.start()
        self.listener = _make_listener(start_enabled=True)

    def tearDown(self) -> None:
        self.listener.shutdown()
        self._patcher.stop()

    def test_no_decode_result_emits_no_messages(self) -> None:
        """None return from ggwave.decode → zero bus messages emitted."""
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        self.assertFalse(
            any(m.msg_type == "recognizer_loop:utterance" for m in msgs)
        )
        self.assertFalse(any(m.msg_type == "speak" for m in msgs))


class TestGGWaveEnableDisableViaBus(unittest.TestCase):
    """ovos.ggwave.enable / ovos.ggwave.disable toggle the plugin at runtime."""

    def setUp(self) -> None:
        self._patcher = patch.object(_ggwave_mod, "decode",
                                     MagicMock(return_value=None))
        self._patcher.start()
        self.listener = _make_listener(start_enabled=True)

    def tearDown(self) -> None:
        self.listener.shutdown()
        self._patcher.stop()

    def test_disable_then_enable_via_bus(self) -> None:
        """Disable via bus → utterance suppressed; re-enable → utterance emitted."""
        # Disable
        self.listener.bus.emit(Message("ovos.ggwave.disable"))
        _ggwave_mod.decode.return_value = b"UTT:blocked utterance"
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        self.assertFalse(
            any(m.msg_type == "recognizer_loop:utterance" for m in msgs),
            "Utterance should be suppressed after disable",
        )

        # Re-enable
        self.listener.bus.emit(Message("ovos.ggwave.enable"))
        _ggwave_mod.decode.return_value = b"UTT:allowed utterance"
        msgs = self.listener.feed_audio(_AUDIO_CHUNK)
        self.assertTrue(
            any(m.msg_type == "recognizer_loop:utterance" for m in msgs),
            "Utterance should be emitted after re-enable",
        )


class TestListenerTestDataclass(unittest.TestCase):
    """Verify the ListenerTest declarative helper works correctly."""

    def test_declarative_utt_test_passes(self) -> None:
        """ListenerTest.execute() passes when expected message type is emitted."""
        from ovos_audio_transformer_plugin_ggwave import GGWavePlugin
        from ovoscope.listener import ListenerTest

        with patch.object(_ggwave_mod, "decode",
                          MagicMock(return_value=b"UTT:hello")):
            with patch("ovos_utils.create_daemon"):
                plugin = GGWavePlugin(config={"start_enabled": True})

            test = ListenerTest(
                plugin_instances={PLUGIN_NAME: plugin},
                audio_input=_AUDIO_CHUNK,
                expected_types=["recognizer_loop:utterance"],
            )
            msgs = test.execute()
        self.assertTrue(any(m.msg_type == "recognizer_loop:utterance" for m in msgs))

    def test_declarative_test_fails_on_missing_type(self) -> None:
        """ListenerTest.execute() raises AssertionError when expected type absent."""
        from ovos_audio_transformer_plugin_ggwave import GGWavePlugin
        from ovoscope.listener import ListenerTest

        with patch.object(_ggwave_mod, "decode", MagicMock(return_value=None)):
            with patch("ovos_utils.create_daemon"):
                plugin = GGWavePlugin(config={"start_enabled": True})

            test = ListenerTest(
                plugin_instances={PLUGIN_NAME: plugin},
                audio_input=_AUDIO_CHUNK,
                expected_types=["recognizer_loop:utterance"],
            )
            with self.assertRaises(AssertionError):
                test.execute()


if __name__ == "__main__":
    unittest.main()
