import warnings

import ggwave
from ovos_bus_client.message import Message
from ovos_config import Configuration
from ovos_plugin_manager.templates.transformers import AudioTransformer
from ovos_utils.log import LOG, init_service_logger


class GGWavePlugin(AudioTransformer):
    """AudioTransformer plugin that decodes ggwave audio payloads.

    Audio chunks are received via :meth:`on_audio` from the OVOS listener
    (e.g. ovos-dinkum-listener) and decoded by the ggwave C library.
    Decoded payloads are dispatched to opcode-specific handlers that emit
    the corresponding OVOS MessageBus events.

    The plugin is gated by :attr:`user_enabled`. When ``False`` (the
    default), decoded payloads are logged and discarded. Enable via the
    companion ``ovos-skill-ggwave`` voice interface or by setting
    ``start_enabled: true`` in the plugin configuration.
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialise the plugin.

        Args:
            config: Optional plugin configuration dictionary.
                Recognised keys:
                - ``start_enabled`` (bool): If ``True``, accept payloads
                  immediately without a voice-enable command. Default ``False``.
        """
        config = config or {}
        super().__init__("ovos-audio-transformer-plugin-ggwave", 10, config)

        # TODO - individual config to enable/disable each
        self.OPCODES: dict = {
            "SSID:": self.handle_wifi_ssid,
            "PSWD:": self.handle_wifi_pswd,
            "UTT:": self.handle_utt,
            "SPEAK:": self.handle_speak,
            "JSON:": self.handle_json,
            "BUS:": self.handle_bus,
            "GHS:": self.handle_skill,
            "PIP:": self.handle_pip,
            "RMPIP:": self.handle_remove_pip,
            # Service-targeted pip opcodes (container-aware installs).
            # Format:  SPIP:<service_name>:<package>
            # Example: SPIP:ovos_audio:ovos-tts-plugin-piper
            # Emits:   ovos.pip.install.<service_name>
            "SPIP:": self.handle_service_pip,
            "RMSPIP:": self.handle_service_remove_pip,
        }
        self._ssid: str | None = None
        self.user_enabled: bool = self.config.get("start_enabled", False)
        self.ggwave = ggwave.init()

    def bind(self, bus=None) -> None:
        """Attach to the MessageBus and register enable/disable handlers.

        Args:
            bus: OVOS MessageBus client instance.
        """
        super().bind(bus)
        # The companion ovos-skill-ggwave emits these messages in response
        # to user voice commands.
        self.bus.on("ovos.ggwave.enable", self.handle_enable)
        self.bus.on("ovos.ggwave.disable", self.handle_disable)

    def handle_enable(self, message: Message) -> None:
        """Handle the ``ovos.ggwave.enable`` bus event.

        Sets :attr:`user_enabled` to ``True``, emits ``ovos.ggwave.enabled``
        back on the bus, and plays an acknowledgement sound.

        Args:
            message: The triggering bus message.
        """
        self.user_enabled = True
        self.bus.emit(message.forward("ovos.ggwave.enabled"))
        # TODO - dedicated sound
        self.bus.emit(Message("mycroft.audio.play_sound",
                              {"uri": "snd/acknowledge.mp3"}))

    def handle_disable(self, message: Message) -> None:
        """Handle the ``ovos.ggwave.disable`` bus event.

        Sets :attr:`user_enabled` to ``False``, emits ``ovos.ggwave.disabled``
        back on the bus, and plays an acknowledgement sound.

        Args:
            message: The triggering bus message.
        """
        self.user_enabled = False
        self.bus.emit(message.forward("ovos.ggwave.disabled"))
        # TODO - dedicated sound
        self.bus.emit(Message("mycroft.audio.play_sound",
                              {"uri": "snd/acknowledge.mp3"}))

    def handle_skill(self, payload: str) -> None:
        """Install a GitHub skill from a URL or ``<org>/<repo>`` shorthand.

        Args:
            payload: Full GitHub URL or ``<org>/<repo>`` shorthand string.
        """
        if not payload.startswith("https://github.com/"):
            payload = f"https://github.com/{payload}"
        LOG.info(f"github skill to install: {payload}")
        self.bus.emit(Message("ovos.skills.install", {"url": payload}))

    def handle_pip(self, payload: str) -> None:
        """Install a PyPI package globally via the OVOS pip installer.

        Args:
            payload: PyPI package name.
        """
        LOG.info(f"pip package to install: {payload}")
        self.bus.emit(Message("ovos.pip.install",
                              {"packages": [payload]}))

    def handle_remove_pip(self, payload: str) -> None:
        """Uninstall a PyPI package globally via the OVOS pip installer.

        Args:
            payload: PyPI package name to uninstall.
        """
        LOG.info(f"pip package to uninstall: {payload}")
        self.bus.emit(Message("ovos.pip.uninstall",
                              {"packages": [payload]}))

    def handle_service_pip(self, payload: str) -> None:
        """Install a package in a specific service container.

        Expected payload format: ``<service_name>:<package>``.

        Example::

            SPIP:ovos_audio:ovos-tts-plugin-piper

        Emits ``ovos.pip.install.<service_name>`` so only the targeted
        service's :class:`~ovos_utils.skill_installer.ServiceInstaller`
        responds.

        Args:
            payload: ``<service_name>:<package>`` string.
        """
        if ":" not in payload:
            LOG.error(f"SPIP payload missing service separator: {payload!r}")
            return
        service_name, _, package = payload.partition(":")
        service_name = service_name.strip()
        package = package.strip()
        if not service_name or not package:
            LOG.error(f"SPIP payload malformed: {payload!r}")
            return
        LOG.info(f"targeted pip install: service={service_name} pkg={package}")
        self.bus.emit(
            Message(f"ovos.pip.install.{service_name}", {"packages": [package]})
        )

    def handle_service_remove_pip(self, payload: str) -> None:
        """Uninstall a package from a specific service container.

        Expected payload format: ``<service_name>:<package>``.

        Example::

            RMSPIP:ovos_audio:ovos-tts-plugin-piper

        Emits ``ovos.pip.uninstall.<service_name>`` so only the targeted
        service responds.

        Args:
            payload: ``<service_name>:<package>`` string.
        """
        if ":" not in payload:
            LOG.error(f"RMSPIP payload missing service separator: {payload!r}")
            return
        service_name, _, package = payload.partition(":")
        service_name = service_name.strip()
        package = package.strip()
        if not service_name or not package:
            LOG.error(f"RMSPIP payload malformed: {payload!r}")
            return
        LOG.info(
            f"targeted pip uninstall: service={service_name} pkg={package}"
        )
        self.bus.emit(
            Message(
                f"ovos.pip.uninstall.{service_name}", {"packages": [package]}
            )
        )

    def handle_bus(self, payload: str) -> None:
        """Emit an arbitrary bus message whose type is the payload string.

        Args:
            payload: Message type string to emit.
        """
        LOG.info(f"bus msg_type: {payload}")
        self.bus.emit(Message(payload))

    def handle_utt(self, payload: str) -> None:
        """Inject an utterance into the OVOS intent pipeline.

        Args:
            payload: Utterance text to inject.
        """
        LOG.info(f"Utterance: {payload}")
        self.bus.emit(Message("recognizer_loop:utterance",
                              {"utterances": [payload]}))

    def handle_wifi_ssid(self, payload: str) -> None:
        """Store the Wi-Fi SSID received via the ``SSID:`` opcode.

        The SSID is cached in :attr:`_ssid` until the ``PSWD:`` opcode
        arrives. Plays the configured ``wifi_ap`` sound if set.

        Args:
            payload: Wi-Fi network name (SSID).
        """
        LOG.info(f"Wifi AP: {payload}")
        self._ssid = payload
        snd = Configuration().get("sounds", {}).get("wifi_ap")
        if snd:  # no sound by default
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

    def handle_speak(self, payload: str) -> None:
        """Emit a ``speak`` bus message to trigger TTS.

        Args:
            payload: Text to speak.
        """
        LOG.info(f"Speak: {payload}")
        self.bus.emit(Message("speak", {"utterance": payload}))

    def handle_json(self, payload: str) -> None:
        """Deserialize a JSON-encoded Message and emit it on the bus.

        If deserialization fails, plays the configured ``json_error`` sound.

        Args:
            payload: Serialized :class:`~ovos_bus_client.message.Message` JSON string.
        """
        LOG.info(f"JSON: {payload}")
        try:
            msg = Message.deserialize(payload)
            self.bus.emit(msg)
        except Exception:
            LOG.exception("failed to deserialize message")
            snd = Configuration().get("sounds", {}).get("json_error", "snd/error.mp3")
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

    def handle_wifi_pswd(self, payload: str) -> None:
        """Connect to Wi-Fi using the previously stored SSID.

        Must be preceded by a ``SSID:`` payload that set :attr:`_ssid`.
        An empty *payload* indicates an open (password-free) network.

        Args:
            payload: Wi-Fi password, or empty string for an open network.
        """
        if not self._ssid:
            LOG.error("received wifi password but wifi SSID not set! ignoring")
            snd = Configuration().get("sounds", {}).get("wifi_error", "snd/error.mp3")
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))
            return

        if not payload:
            LOG.info("wifi is open, no password")
            data = {"connection_name": self._ssid}
            self.bus.emit(Message("ovos.phal.nm.connect.open.network", data))
        else:
            LOG.info(f"Wifi PSWD {payload}")
            data = {"connection_name": self._ssid, "password": payload}
            self.bus.emit(Message("ovos.phal.nm.connect", data))

        self._ssid = None

    def _dispatch_payload(self, payload: str) -> None:
        """Dispatch a decoded ggwave payload to the matching opcode handler.

        Plays a success sound on recognition and an error sound for unknown
        opcodes. Payloads are silently dropped when :attr:`user_enabled` is
        ``False``.

        Args:
            payload: Decoded UTF-8 string from ggwave.
        """
        snd = Configuration().get("sounds", {}).get("ggwave_success", "snd/acknowledge.mp3")
        if snd:
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

        for opcode, handler in self.OPCODES.items():
            if payload.startswith(opcode):
                arg = payload.split(opcode, 1)[-1]
                if self.user_enabled:
                    handler(arg)
                else:
                    LOG.info("ignoring ggwave payload, user did not enable ggwave")
                return

        LOG.debug(f"invalid ggwave payload: {payload}")
        snd = Configuration().get("sounds", {}).get("ggwave_error")
        if snd:
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

    def on_audio(self, audio_data: bytes) -> bytes:
        """Process a non-speech audio chunk from the OVOS listener.

        Passes each chunk to :func:`ggwave.decode`. When a complete payload
        is recognised, :meth:`_dispatch_payload` is called.

        Args:
            audio_data: Raw audio bytes from the listener (typically 16 kHz,
                16-bit PCM or float32, 1024 frames per chunk).

        Returns:
            The original *audio_data* unchanged (pass-through).
        """
        try:
            res = ggwave.decode(self.ggwave, audio_data)
            if res is not None:
                try:
                    payload = res.decode("utf-8")
                    self._dispatch_payload(payload)
                except Exception:
                    LOG.exception("ggwave payload decode/dispatch failed")
        except Exception:
            LOG.exception("ggwave.decode failed")
        return audio_data

    def default_shutdown(self) -> None:
        """Release the native ggwave context on shutdown."""
        ggwave.free(self.ggwave)


def launch_cli() -> None:
    """Start the plugin as a standalone process.

    .. deprecated::
        The standalone mode is deprecated. Use the plugin via the OVOS
        audio transformer pipeline (ovos-dinkum-listener) instead.
        This function will be removed in a future release.
    """
    warnings.warn(
        "launch_cli() is deprecated. Run the plugin through the OVOS audio "
        "transformer pipeline (ovos-dinkum-listener) instead of standalone mode.",
        DeprecationWarning,
        stacklevel=2,
    )
    from ovos_utils import wait_for_exit_signal
    from ovos_bus_client.util import get_mycroft_bus
    init_service_logger("ggwave")

    gg = GGWavePlugin({"start_enabled": True})

    bus = get_mycroft_bus()
    gg.bind(bus)

    wait_for_exit_signal()  # wait for CTRl+C


if __name__ == "__main__":
    launch_cli()
