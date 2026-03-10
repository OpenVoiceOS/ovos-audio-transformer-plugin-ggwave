# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""Unit tests for GGWavePlugin.

Tests all opcode handlers and bus interaction logic in isolation using FakeBus.
The pyaudio monitor thread and the ggwave C library are mocked so tests run
without audio hardware or the native ggwave extension.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub native modules that are not available in the test environment.
# Must happen before importing the plugin package.
# ---------------------------------------------------------------------------
_ggwave_stub = types.ModuleType("ggwave")
_ggwave_stub.init = MagicMock(return_value=MagicMock())
_ggwave_stub.free = MagicMock()
_ggwave_stub.decode = MagicMock(return_value=None)
sys.modules.setdefault("ggwave", _ggwave_stub)

_pyaudio_stub = types.ModuleType("pyaudio")
_pyaudio_stub.PyAudio = MagicMock()
_pyaudio_stub.paFloat32 = 1
sys.modules.setdefault("pyaudio", _pyaudio_stub)

from ovos_utils.fakebus import FakeBus  # noqa: E402
from ovos_bus_client.message import Message  # noqa: E402


def _make_plugin() -> "GGWavePlugin":
    """Instantiate GGWavePlugin with ggwave and pyaudio mocked out."""
    from ovos_audio_transformer_plugin_ggwave import GGWavePlugin
    return GGWavePlugin(config={"start_enabled": False})


def _bind(plugin: "GGWavePlugin") -> FakeBus:
    """Bind *plugin* to a FakeBus and return the bus."""
    bus = FakeBus()
    with patch("ovos_utils.create_daemon"):
        plugin.bind(bus)
    return bus


class TestGGWavePluginInit(unittest.TestCase):
    """Tests for __init__ and bind."""

    def test_user_enabled_defaults_to_config_start_enabled_false(self) -> None:
        """user_enabled is False when start_enabled not set in config."""
        plugin = _make_plugin()
        self.assertFalse(plugin.user_enabled)

    def test_user_enabled_true_when_start_enabled_config(self) -> None:
        """user_enabled is True when start_enabled=True in config."""
        from ovos_audio_transformer_plugin_ggwave import GGWavePlugin
        plugin = GGWavePlugin(config={"start_enabled": True})
        self.assertTrue(plugin.user_enabled)

    def test_opcodes_all_present(self) -> None:
        """All expected opcode prefixes are registered in self.OPCODES."""
        plugin = _make_plugin()
        expected = {"SSID:", "PSWD:", "UTT:", "SPEAK:", "JSON:",
                    "BUS:", "GHS:", "PIP:", "RMPIP:", "SPIP:", "RMSPIP:"}
        self.assertEqual(set(plugin.OPCODES.keys()), expected)

    def test_bind_registers_enable_disable_handlers(self) -> None:
        """bind() registers handlers for ovos.ggwave.enable/disable on the bus."""
        plugin = _make_plugin()
        bus = _bind(plugin)
        self.assertTrue(len(bus.ee.listeners("ovos.ggwave.enable")) > 0)
        self.assertTrue(len(bus.ee.listeners("ovos.ggwave.disable")) > 0)


class TestHandleEnableDisable(unittest.TestCase):
    """Tests for handle_enable and handle_disable."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_enable_sets_user_enabled_true(self) -> None:
        """handle_enable sets user_enabled = True."""
        self.plugin.handle_enable(Message("ovos.ggwave.enable"))
        self.assertTrue(self.plugin.user_enabled)

    def test_handle_enable_emits_enabled_event(self) -> None:
        """handle_enable emits ovos.ggwave.enabled on the bus."""
        received: list[Message] = []
        self.bus.on("ovos.ggwave.enabled", lambda m: received.append(m))
        self.plugin.handle_enable(Message("ovos.ggwave.enable"))
        self.assertEqual(len(received), 1)

    def test_handle_enable_emits_acknowledge_sound(self) -> None:
        """handle_enable emits mycroft.audio.play_sound with acknowledge.mp3."""
        received: list[Message] = []
        self.bus.on("mycroft.audio.play_sound", lambda m: received.append(m))
        self.plugin.handle_enable(Message("ovos.ggwave.enable"))
        self.assertTrue(any("acknowledge" in m.data.get("uri", "") for m in received))

    def test_handle_disable_sets_user_enabled_false(self) -> None:
        """handle_disable sets user_enabled = False."""
        self.plugin.user_enabled = True
        self.plugin.handle_disable(Message("ovos.ggwave.disable"))
        self.assertFalse(self.plugin.user_enabled)

    def test_handle_disable_emits_disabled_event(self) -> None:
        """handle_disable emits ovos.ggwave.disabled on the bus."""
        received: list[Message] = []
        self.bus.on("ovos.ggwave.disabled", lambda m: received.append(m))
        self.plugin.handle_disable(Message("ovos.ggwave.disable"))
        self.assertEqual(len(received), 1)

    def test_handle_disable_emits_acknowledge_sound(self) -> None:
        """handle_disable emits mycroft.audio.play_sound with acknowledge.mp3."""
        received: list[Message] = []
        self.bus.on("mycroft.audio.play_sound", lambda m: received.append(m))
        self.plugin.handle_disable(Message("ovos.ggwave.disable"))
        self.assertTrue(any("acknowledge" in m.data.get("uri", "") for m in received))


class TestHandleUtt(unittest.TestCase):
    """Tests for handle_utt opcode handler."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_utt_emits_recognizer_loop_utterance(self) -> None:
        """handle_utt emits recognizer_loop:utterance with the payload text."""
        received: list[Message] = []
        self.bus.on("recognizer_loop:utterance", lambda m: received.append(m))
        self.plugin.handle_utt("turn off the lights")
        self.assertEqual(len(received), 1)
        self.assertIn("turn off the lights", received[0].data["utterances"])


class TestHandleSpeak(unittest.TestCase):
    """Tests for handle_speak opcode handler."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_speak_emits_speak_message(self) -> None:
        """handle_speak emits a speak message with the payload as utterance."""
        received: list[Message] = []
        self.bus.on("speak", lambda m: received.append(m))
        self.plugin.handle_speak("hello there")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["utterance"], "hello there")


class TestHandleBus(unittest.TestCase):
    """Tests for handle_bus opcode handler."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_bus_emits_arbitrary_message_type(self) -> None:
        """handle_bus emits any message type string received as payload."""
        received: list[Message] = []
        self.bus.on("my.custom.message", lambda m: received.append(m))
        self.plugin.handle_bus("my.custom.message")
        self.assertEqual(len(received), 1)


class TestHandlePip(unittest.TestCase):
    """Tests for handle_pip and handle_remove_pip."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_pip_emits_ovos_pip_install(self) -> None:
        """handle_pip emits ovos.pip.install with the package name."""
        received: list[Message] = []
        self.bus.on("ovos.pip.install", lambda m: received.append(m))
        self.plugin.handle_pip("ovos-tts-plugin-piper")
        self.assertEqual(len(received), 1)
        self.assertIn("ovos-tts-plugin-piper", received[0].data["packages"])

    def test_handle_remove_pip_emits_ovos_pip_uninstall(self) -> None:
        """handle_remove_pip emits ovos.pip.uninstall with the package name."""
        received: list[Message] = []
        self.bus.on("ovos.pip.uninstall", lambda m: received.append(m))
        self.plugin.handle_remove_pip("ovos-tts-plugin-piper")
        self.assertEqual(len(received), 1)
        self.assertIn("ovos-tts-plugin-piper", received[0].data["packages"])


class TestHandleServicePip(unittest.TestCase):
    """Tests for handle_service_pip and handle_service_remove_pip."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_service_pip_emits_targeted_install(self) -> None:
        """handle_service_pip emits ovos.pip.install.<service>."""
        received: list[Message] = []
        self.bus.on("ovos.pip.install.ovos_audio", lambda m: received.append(m))
        self.plugin.handle_service_pip("ovos_audio:ovos-tts-plugin-piper")
        self.assertEqual(len(received), 1)
        self.assertIn("ovos-tts-plugin-piper", received[0].data["packages"])

    def test_handle_service_pip_missing_separator_logs_error(self) -> None:
        """handle_service_pip does nothing and logs error when ':' is absent."""
        received: list[Message] = []
        self.bus.on("ovos.pip.install.anything", lambda m: received.append(m))
        self.plugin.handle_service_pip("no-separator-here")
        self.assertEqual(len(received), 0)

    def test_handle_service_pip_empty_service_name_logs_error(self) -> None:
        """handle_service_pip does nothing when service name is empty."""
        received: list[Message] = []
        self.plugin.handle_service_pip(":some-package")
        self.assertEqual(len(received), 0)

    def test_handle_service_pip_empty_package_logs_error(self) -> None:
        """handle_service_pip does nothing when package name is empty."""
        received: list[Message] = []
        self.plugin.handle_service_pip("ovos_audio:")
        self.assertEqual(len(received), 0)

    def test_handle_service_remove_pip_emits_targeted_uninstall(self) -> None:
        """handle_service_remove_pip emits ovos.pip.uninstall.<service>."""
        received: list[Message] = []
        self.bus.on("ovos.pip.uninstall.ovos_audio", lambda m: received.append(m))
        self.plugin.handle_service_remove_pip("ovos_audio:ovos-tts-plugin-piper")
        self.assertEqual(len(received), 1)
        self.assertIn("ovos-tts-plugin-piper", received[0].data["packages"])

    def test_handle_service_remove_pip_missing_separator_logs_error(self) -> None:
        """handle_service_remove_pip does nothing when ':' is absent."""
        received: list[Message] = []
        self.plugin.handle_service_remove_pip("no-separator")
        self.assertEqual(len(received), 0)


class TestHandleSkill(unittest.TestCase):
    """Tests for handle_skill opcode handler."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_skill_emits_ovos_skills_install_with_full_url(self) -> None:
        """handle_skill with a full GitHub URL emits ovos.skills.install."""
        received: list[Message] = []
        self.bus.on("ovos.skills.install", lambda m: received.append(m))
        self.plugin.handle_skill("https://github.com/OpenVoiceOS/ovos-skill-hello-world")
        self.assertEqual(len(received), 1)
        self.assertIn("ovos-skill-hello-world", received[0].data["url"])

    def test_handle_skill_prepends_github_url_for_short_name(self) -> None:
        """handle_skill without https:// prefix prepends the GitHub base URL."""
        received: list[Message] = []
        self.bus.on("ovos.skills.install", lambda m: received.append(m))
        self.plugin.handle_skill("OpenVoiceOS/ovos-skill-hello-world")
        self.assertEqual(len(received), 1)
        self.assertTrue(received[0].data["url"].startswith("https://github.com/"))


class TestHandleWifi(unittest.TestCase):
    """Tests for handle_wifi_ssid and handle_wifi_pswd."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_wifi_ssid_stores_ssid(self) -> None:
        """handle_wifi_ssid stores the SSID for later use by handle_wifi_pswd."""
        self.plugin.handle_wifi_ssid("MyNetwork")
        self.assertEqual(self.plugin._ssid, "MyNetwork")

    def test_handle_wifi_pswd_emits_open_network_when_no_password(self) -> None:
        """handle_wifi_pswd with empty password emits ovos.phal.nm.connect.open.network."""
        self.plugin._ssid = "OpenNetwork"
        received: list[Message] = []
        self.bus.on("ovos.phal.nm.connect.open.network", lambda m: received.append(m))
        self.plugin.handle_wifi_pswd("")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["connection_name"], "OpenNetwork")
        self.assertIsNone(self.plugin._ssid)

    def test_handle_wifi_pswd_emits_connect_with_password(self) -> None:
        """handle_wifi_pswd with password emits ovos.phal.nm.connect."""
        self.plugin._ssid = "SecureNet"
        received: list[Message] = []
        self.bus.on("ovos.phal.nm.connect", lambda m: received.append(m))
        self.plugin.handle_wifi_pswd("s3cr3t")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["connection_name"], "SecureNet")
        self.assertEqual(received[0].data["password"], "s3cr3t")
        self.assertIsNone(self.plugin._ssid)

    def test_handle_wifi_pswd_without_ssid_emits_error_sound(self) -> None:
        """handle_wifi_pswd with no prior SSID emits an error sound."""
        self.plugin._ssid = None
        received: list[Message] = []
        self.bus.on("mycroft.audio.play_sound", lambda m: received.append(m))
        self.plugin.handle_wifi_pswd("password")
        self.assertTrue(len(received) > 0)


class TestHandleJson(unittest.TestCase):
    """Tests for handle_json opcode handler."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)

    def test_handle_json_deserializes_and_emits_message(self) -> None:
        """handle_json deserializes a JSON message string and emits it on the bus."""
        received: list[Message] = []
        self.bus.on("my.json.message", lambda m: received.append(m))
        msg = Message("my.json.message", {"key": "value"})
        self.plugin.handle_json(msg.serialize())
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["key"], "value")

    def test_handle_json_emits_error_sound_on_invalid_json(self) -> None:
        """handle_json emits a sound on deserialization failure."""
        received: list[Message] = []
        self.bus.on("mycroft.audio.play_sound", lambda m: received.append(m))
        self.plugin.handle_json("not valid json {{{{")
        self.assertTrue(len(received) > 0)


class TestOnAudio(unittest.TestCase):
    """Tests for on_audio and _dispatch_payload."""

    def setUp(self) -> None:
        self.plugin = _make_plugin()
        self.bus = _bind(self.plugin)
        self.plugin.user_enabled = True

    def test_on_audio_returns_audio_data_unchanged(self) -> None:
        """on_audio always returns the original audio bytes."""
        _ggwave_stub.decode = MagicMock(return_value=None)
        data = b"\x00" * 2048
        result = self.plugin.on_audio(data)
        self.assertEqual(result, data)

    def test_on_audio_dispatches_decoded_payload(self) -> None:
        """on_audio calls _dispatch_payload when ggwave.decode returns data."""
        _ggwave_stub.decode = MagicMock(return_value=b"SPEAK:hello")
        received: list[Message] = []
        self.bus.on("speak", lambda m: received.append(m))
        self.plugin.on_audio(b"\x00" * 1024)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["utterance"], "hello")

    def test_on_audio_no_dispatch_when_decode_returns_none(self) -> None:
        """on_audio does nothing when ggwave.decode returns None."""
        _ggwave_stub.decode = MagicMock(return_value=None)
        received: list[Message] = []
        self.bus.on("speak", lambda m: received.append(m))
        self.plugin.on_audio(b"\x00" * 1024)
        self.assertEqual(len(received), 0)

    def test_dispatch_payload_gated_when_user_disabled(self) -> None:
        """_dispatch_payload drops the payload when user_enabled is False."""
        self.plugin.user_enabled = False
        received: list[Message] = []
        self.bus.on("recognizer_loop:utterance", lambda m: received.append(m))
        self.plugin._dispatch_payload("UTT:turn on the lights")
        self.assertEqual(len(received), 0)

    def test_dispatch_payload_dispatches_when_user_enabled(self) -> None:
        """_dispatch_payload dispatches to the handler when user_enabled is True."""
        received: list[Message] = []
        self.bus.on("recognizer_loop:utterance", lambda m: received.append(m))
        self.plugin._dispatch_payload("UTT:turn on the lights")
        self.assertEqual(len(received), 1)

    def test_dispatch_payload_unknown_opcode_logs_debug(self) -> None:
        """_dispatch_payload handles unknown opcodes without raising."""
        # Should not raise; just logs debug
        self.plugin._dispatch_payload("UNKNOWN:some payload")


class TestDefaultShutdown(unittest.TestCase):
    """Tests for default_shutdown."""

    def test_default_shutdown_releases_ggwave_context(self) -> None:
        """default_shutdown calls ggwave.free exactly once."""
        import ggwave as _gg
        original_free = _gg.free
        mock_free = MagicMock()
        _gg.free = mock_free
        try:
            plugin = _make_plugin()
            _bind(plugin)
            plugin.default_shutdown()
            mock_free.assert_called_once()
        finally:
            _gg.free = original_free

    def test_default_shutdown_calls_ggwave_free(self) -> None:
        """default_shutdown calls ggwave.free to release native resources."""
        import ggwave as _gg
        original_free = _gg.free
        mock_free = MagicMock()
        _gg.free = mock_free
        try:
            plugin = _make_plugin()
            _bind(plugin)
            plugin.default_shutdown()
            mock_free.assert_called_once_with(plugin.ggwave)
        finally:
            _gg.free = original_free


if __name__ == "__main__":
    unittest.main()
