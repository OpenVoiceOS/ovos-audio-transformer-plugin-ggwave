# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""Tests for the self-disabling listen timeout security hardening.

The ggwave listener is off by default; once a user enables it, the plugin
must auto-disable after `listen_timeout` seconds so a stray/forgotten enable
does not leave data-over-sound listening on forever.
"""
import time
import unittest

from ovos_bus_client.message import Message
from ovoscope.listener import get_mini_listener

from ovos_audio_transformer_plugin_ggwave import GGWavePlugin

PLUGIN_NAME = "ovos-audio-transformer-plugin-ggwave"


def _listener(listen_timeout=300, enabled=False):
    plugin = GGWavePlugin(
        config={"start_enabled": enabled, "sample_rate": 16000,
                "listen_timeout": listen_timeout}
    )
    return get_mini_listener(plugin_instances={PLUGIN_NAME: plugin}), plugin


class TestListenTimeout(unittest.TestCase):

    def test_enable_auto_disables_after_timeout(self):
        """Enabling arms a timer; after it elapses the listener turns off."""
        listener, plugin = _listener(listen_timeout=0.2, enabled=False)
        try:
            listener._messages.clear()
            listener.bus.emit(Message("ovos.ggwave.enable"))
            self.assertTrue(plugin.user_enabled)
            time.sleep(0.4)
            self.assertFalse(plugin.user_enabled)
            types = [m.msg_type for m in listener._messages]
            self.assertIn("ovos.ggwave.disabled", types)
        finally:
            listener.shutdown()

    def test_explicit_disable_cancels_pending_timer(self):
        """Disabling before the timeout fires cancels it (no double emit)."""
        listener, plugin = _listener(listen_timeout=0.2, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable"))
            listener._messages.clear()
            listener.bus.emit(Message("ovos.ggwave.disable"))
            self.assertFalse(plugin.user_enabled)
            # wait past the original deadline; must not fire again
            time.sleep(0.4)
            types = [m.msg_type for m in listener._messages]
            self.assertEqual(types.count("ovos.ggwave.disabled"), 1)
            self.assertFalse(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_reenable_resets_countdown(self):
        """Re-enabling before the deadline resets the timeout window."""
        listener, plugin = _listener(listen_timeout=0.3, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable"))
            time.sleep(0.2)
            listener.bus.emit(Message("ovos.ggwave.enable"))  # reset countdown
            # original deadline (0.3s after first enable) has now passed,
            # but the reset means it should still be enabled
            time.sleep(0.2)
            self.assertTrue(plugin.user_enabled)
            # let the (reset) timer actually fire to confirm it was armed
            time.sleep(0.3)
            self.assertFalse(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_enable_message_timeout_override(self):
        """A `timeout` field on the enable message overrides the config default."""
        listener, plugin = _listener(listen_timeout=300, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable", {"timeout": 0.2}))
            self.assertTrue(plugin.user_enabled)
            time.sleep(0.4)
            self.assertFalse(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_listen_timeout_zero_disables_auto_disable(self):
        """listen_timeout = 0 means the listener never auto-disables."""
        listener, plugin = _listener(listen_timeout=0, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable"))
            self.assertTrue(plugin.user_enabled)
            self.assertIsNone(plugin._timeout_timer)
            time.sleep(0.3)
            self.assertTrue(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_start_enabled_config_does_not_arm_timer(self):
        """`start_enabled: true` is an explicit always-on decision, not armed."""
        listener, plugin = _listener(listen_timeout=0.2, enabled=True)
        try:
            self.assertTrue(plugin.user_enabled)
            self.assertIsNone(plugin._timeout_timer)
            time.sleep(0.4)
            self.assertTrue(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_bus_enable_arms_timer(self):
        """Bus-driven enable arms the timer (contrast with config enable)."""
        listener, plugin = _listener(listen_timeout=300, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable"))
            self.assertIsNotNone(plugin._timeout_timer)
        finally:
            listener.shutdown()

    def test_auto_disable_forwards_enabling_session(self):
        """The auto-disable announcement must land in the enabling session."""
        listener, plugin = _listener(listen_timeout=0.2, enabled=False)
        try:
            listener._messages.clear()
            msg = Message("ovos.ggwave.enable", context={
                "session": {"session_id": "remote-peer-42"}})
            listener.bus.emit(msg)
            time.sleep(0.4)
            disabled = [m for m in listener._messages
                        if m.msg_type == "ovos.ggwave.disabled"]
            self.assertTrue(disabled)
            sess = disabled[0].context.get("session", {}).get("session_id")
            self.assertEqual(sess, "remote-peer-42")
        finally:
            listener.shutdown()

    def test_requested_timeout_is_capped_by_config(self):
        """A huge requested timeout cannot defeat the configured ceiling."""
        listener, plugin = _listener(listen_timeout=1, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable", {"timeout": 99999}))
            self.assertTrue(plugin.user_enabled)
            time.sleep(1.3)
            self.assertFalse(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_string_listen_timeout_config_is_coerced(self):
        """A stringly-typed `listen_timeout` in config must not crash init."""
        listener, plugin = _listener(listen_timeout="0.2", enabled=False)
        try:
            self.assertEqual(plugin.listen_timeout, 0.2)
            listener.bus.emit(Message("ovos.ggwave.enable"))
            time.sleep(0.4)
            self.assertFalse(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_invalid_listen_timeout_config_falls_back_to_default(self):
        """A garbage `listen_timeout` falls back to the default, not a crash."""
        listener, plugin = _listener(listen_timeout="not-a-number", enabled=False)
        try:
            self.assertEqual(plugin.listen_timeout, 300)
        finally:
            listener.shutdown()

    def test_invalid_bus_timeout_falls_back_to_configured_default(self):
        """A stringly-typed/garbage `timeout` on the enable message is coerced."""
        listener, plugin = _listener(listen_timeout=0.2, enabled=False)
        try:
            listener.bus.emit(Message("ovos.ggwave.enable", {"timeout": "bogus"}))
            self.assertTrue(plugin.user_enabled)
            time.sleep(0.4)
            self.assertFalse(plugin.user_enabled)
        finally:
            listener.shutdown()

    def test_bus_timeout_ignored_when_listen_timeout_off(self):
        """listen_timeout = 0 is an off-switch: a bus-supplied `timeout`
        must not arm a timer that kills an always-on listener."""
        listener, plugin = _listener(listen_timeout=0, enabled=False)
        try:
            listener._messages.clear()
            listener.bus.emit(Message("ovos.ggwave.enable", {"timeout": 0.2}))
            self.assertTrue(plugin.user_enabled)
            self.assertIsNone(plugin._timeout_timer)
            time.sleep(0.5)
            self.assertTrue(plugin.user_enabled)
            types = [m.msg_type for m in listener._messages]
            self.assertNotIn("ovos.ggwave.disabled", types)
        finally:
            listener.shutdown()

    def test_bus_timeout_ignored_when_listen_timeout_negative(self):
        """listen_timeout = -1 is also an off-switch for bus-supplied timeouts."""
        listener, plugin = _listener(listen_timeout=-1, enabled=False)
        try:
            listener._messages.clear()
            listener.bus.emit(Message("ovos.ggwave.enable", {"timeout": 0.2}))
            self.assertTrue(plugin.user_enabled)
            self.assertIsNone(plugin._timeout_timer)
            time.sleep(0.5)
            self.assertTrue(plugin.user_enabled)
            types = [m.msg_type for m in listener._messages]
            self.assertNotIn("ovos.ggwave.disabled", types)
        finally:
            listener.shutdown()

    def test_stale_auto_disable_callback_is_ignored(self):
        """A superseded (stale) timer callback must not disable the listener.

        This deterministically simulates the race where a fresh re-arm bumps
        the generation counter after an old timer's callback was already
        scheduled to run: invoking the stale callback directly (with the old
        generation number) must be a no-op.
        """
        listener, plugin = _listener(listen_timeout=300, enabled=False)
        try:
            plugin._arm_timeout(0.2)
            stale_gen = plugin._timeout_gen
            plugin._arm_timeout(300)  # bumps the generation, supersedes stale_gen
            self.assertNotEqual(stale_gen, plugin._timeout_gen)

            plugin.user_enabled = True
            listener._messages.clear()
            plugin._auto_disable(stale_gen)  # simulate the stale timer firing

            self.assertTrue(plugin.user_enabled)
            types = [m.msg_type for m in listener._messages]
            self.assertNotIn("ovos.ggwave.disabled", types)
        finally:
            listener.shutdown()


if __name__ == "__main__":
    unittest.main()
