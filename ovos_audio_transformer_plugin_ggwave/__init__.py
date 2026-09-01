import threading

import ggwave
import numpy as np
from ovos_config import Configuration
from ovos_plugin_manager.templates.transformers import AudioTransformer
from ovos_utils.log import LOG
from ovos_utils.messagebus import Message

# ggwave operates natively at 48kHz float32 (see ggwave.getDefaultParameters)
GGWAVE_SAMPLE_RATE = 48000


class GGWavePlugin(AudioTransformer):

    def __init__(self, config=None):
        config = config or {}
        super().__init__("ovos-audio-transformer-plugin-ggwave", 10, config)

        # TODO - individual config to enable/disable each
        self.OPCODES = {
            "SSID:": self.handle_wifi_ssid,
            "PSWD:": self.handle_wifi_pswd,
            "UTT:": self.handle_utt,
            "SPEAK:": self.handle_speak,
            "JSON:": self.handle_json,
            "BUS:": self.handle_bus,
            "GHS:": self.handle_skill,
            "PIP:": self.handle_pip,
            "RMPIP:": self.handle_remove_pip
        }
        self._ssid = None
        # security hardening: when the listener is enabled over the bus
        # (`ovos.ggwave.enable`), auto-disable after `listen_timeout` seconds
        # so a stray/forgotten enable does not leave data-over-sound
        # listening on forever. 0 (or negative) disables this behavior.
        # `start_enabled: true` in config is an explicit operator decision
        # to run always-on and never arms the timer.
        self.listen_timeout = self._coerce_timeout(
            self.config.get("listen_timeout"), 300)
        self._timeout_timer = None
        self._timeout_lock = threading.Lock()
        self._timeout_gen = 0
        self.user_enabled = self.config.get("start_enabled", False)
        self.ggwave = ggwave.init()
        self._freed = False
        # incoming audio is int16 PCM at the listener's sample rate; ggwave needs
        # 48kHz float32, so we resample each chunk before decoding. Read the rate
        # the same way the listener does (mycroft.conf -> listener.sample_rate).
        listener_conf = Configuration().get("listener", {})
        self.input_rate = self.config.get("sample_rate") or \
            listener_conf.get("sample_rate", 16000)

    @staticmethod
    def _coerce_timeout(value, default):
        """Coerce a config/bus supplied timeout to float, falling back to `default`."""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            LOG.warning(f"invalid listen_timeout value: {value!r}, "
                        f"falling back to {default}")
            return default

    def bind(self, bus=None):
        """ attach messagebus """
        super().bind(bus)
        # we load the voice interface as part of this plugin
        # the skill interacts only via messagebus
        self.bus.on("ovos.ggwave.enable", self.handle_enable)
        self.bus.on("ovos.ggwave.disable", self.handle_disable)

    def _cancel_locked(self):
        """Cancel any pending auto-disable timer. Caller must hold `_timeout_lock`."""
        if self._timeout_timer is not None:
            self._timeout_timer.cancel()
            self._timeout_timer = None

    def _cancel_timeout(self):
        """Cancel any pending auto-disable timer."""
        with self._timeout_lock:
            self._timeout_gen += 1
            self._cancel_locked()

    def _arm_timeout(self, timeout=None, message=None):
        """(Re)arm the auto-disable timer.

        Cancels any timer already running (re-enabling resets the countdown)
        and starts a fresh one, unless the effective timeout is <= 0.
        `message` is the bus message that triggered the enable and is used
        to forward the eventual auto-disable announcement to the same
        session.
        """
        with self._timeout_lock:
            self._cancel_locked()
            if timeout is None:
                timeout = self.listen_timeout
            if timeout is None or timeout <= 0:
                return
            self._timeout_gen += 1
            gen = self._timeout_gen
            self._timeout_timer = threading.Timer(timeout, self._auto_disable,
                                                   args=(gen, message))
            self._timeout_timer.daemon = True
            self._timeout_timer.start()

    def _auto_disable(self, gen, message=None):
        """Fired by the timer once the listen timeout elapses."""
        with self._timeout_lock:
            if gen != self._timeout_gen:
                # superseded by a newer arm/cancel, this callback is stale
                return
            if not self.user_enabled:
                return
            self.user_enabled = False
            self._timeout_timer = None
        LOG.info("ggwave listen timeout reached, auto-disabling listener")
        # forward from the enabling message so the announcement lands in
        # the session that enabled the listener, not a fresh/default one
        if message is not None:
            self.bus.emit(message.forward("ovos.ggwave.disabled"))
            # TODO - dedicated sound
            self.bus.emit(message.forward("mycroft.audio.play_sound",
                                          {"uri": "snd/acknowledge.mp3"}))
        else:
            self.bus.emit(Message("ovos.ggwave.disabled"))
            # TODO - dedicated sound
            self.bus.emit(Message("mycroft.audio.play_sound",
                                  {"uri": "snd/acknowledge.mp3"}))

    def handle_enable(self, message: Message):
        self.user_enabled = True
        # listen_timeout <= 0 is the config off-switch: the listener runs
        # indefinitely and no bus-supplied timeout can override that
        if self.listen_timeout is None or self.listen_timeout <= 0:
            self._cancel_timeout()
        else:
            timeout = self._coerce_timeout(message.data.get("timeout"), self.listen_timeout)
            if timeout <= 0:
                timeout = self.listen_timeout
            # a requested timeout may never exceed the configured ceiling, so a
            # ggwave payload cannot defeat the security hardening by requesting
            # an arbitrarily large timeout
            timeout = min(timeout, self.listen_timeout)
            self._arm_timeout(timeout, message)
        self.bus.emit(message.forward("ovos.ggwave.enabled"))
        # TODO - dedicated sound
        self.bus.emit(Message("mycroft.audio.play_sound",
                              {"uri": "snd/acknowledge.mp3"}))

    def handle_disable(self, message: Message):
        self.user_enabled = False
        self._cancel_timeout()
        self.bus.emit(message.forward("ovos.ggwave.disabled"))
        # TODO - dedicated sound
        self.bus.emit(Message("mycroft.audio.play_sound",
                              {"uri": "snd/acknowledge.mp3"}))

    def handle_skill(self, payload):
        if not payload.startswith("https://github.com/"):
            payload = f"https://github.com/{payload}"
        LOG.info(f"github skill to install: {payload}")
        self.bus.emit(Message("ovos.skills.install", {"url": payload}))

    def handle_pip(self, payload):
        LOG.info(f"pip package to install: {payload}")
        self.bus.emit(Message("ovos.pip.install",
                              {"packages": [payload]}))

    def handle_remove_pip(self, payload):
        LOG.info(f"pip package to uninstall: {payload}")
        self.bus.emit(Message("ovos.pip.uninstall",
                              {"packages": [payload]}))

    def handle_bus(self, payload):
        LOG.info(f"bus msg_type: {payload}")
        self.bus.emit(Message(payload))

    def handle_utt(self, payload):
        LOG.info(f"Utterance: {payload}")
        self.bus.emit(Message("recognizer_loop:utterance",
                              {"utterances": [payload]}))

    def handle_wifi_ssid(self, payload):
        LOG.info(f"Wifi AP: {payload}")
        self._ssid = payload
        snd = Configuration().get("sounds", {}).get("wifi_ap")
        if snd:  # no sound by default
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

    def handle_speak(self, payload):
        LOG.info(f"Speak: {payload}")
        self.bus.emit(Message("speak", {"utterance": payload}))

    def handle_json(self, payload):
        LOG.info(f"JSON: {payload}")
        try:
            msg = Message.deserialize(payload)
            self.bus.emit(msg)
        except:
            LOG.exception("failed to deserialize message")
            snd = Configuration().get("sounds", {}).get("json_error", "snd/error.mp3")
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

    def handle_wifi_pswd(self, payload):
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

    def _to_ggwave_audio(self, audio_data: bytes) -> bytes:
        """Convert a listener audio chunk to ggwave's native format.

        Incoming chunks are int16 PCM at ``self.input_rate``; ggwave decodes
        float32 at 48kHz, so we normalize and (when needed) linearly resample.
        """
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        if self.input_rate != GGWAVE_SAMPLE_RATE and len(samples):
            n_out = int(round(len(samples) * GGWAVE_SAMPLE_RATE / self.input_rate))
            samples = np.interp(np.linspace(0, len(samples) - 1, n_out),
                                np.arange(len(samples)), samples).astype(np.float32)
        return samples.tobytes()

    def on_audio(self, audio_data):
        """Sniff each non-speech audio chunk for ggwave data-over-sound.

        ggwave keeps decode state internally across calls, so each resampled
        chunk is fed straight through; the audio itself is returned unchanged.
        """
        if not audio_data:
            return audio_data
        try:
            res = ggwave.decode(self.ggwave, self._to_ggwave_audio(audio_data))
        except Exception:
            LOG.exception("ggwave decode failed")
            return audio_data
        if res is not None:
            try:
                self._handle_payload(res.decode("utf-8"))
            except Exception:
                LOG.exception("failed to handle ggwave payload")
        return audio_data

    def _handle_payload(self, payload: str):
        """Dispatch a decoded ggwave payload to its opcode handler."""
        snd = Configuration().get("sounds", {}).get("ggwave_success", "snd/acknowledge.mp3")
        if snd:  # play an acknowledgement that *something* was decoded
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

        for opcode, handler in self.OPCODES.items():
            if payload.startswith(opcode):
                data = payload.split(opcode, 1)[-1]
                if self.user_enabled:
                    handler(data)
                else:
                    LOG.info("ignoring ggwave payload, user did not enable ggwave")
                return

        LOG.debug(f"invalid ggwave payload: {payload}")
        snd = Configuration().get("sounds", {}).get("ggwave_error")
        if snd:  # no sound by default
            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

    def default_shutdown(self):
        """ perform any shutdown actions """
        # ggwave allows a limited number of live instances; free ours exactly
        # once. The base AudioTransformer exposes ``default_shutdown`` as the
        # override hook, while the dinkum listener service calls ``shutdown``,
        # so both delegate here and the flag keeps the free idempotent.
        self._cancel_timeout()
        if not self._freed:
            self._freed = True
            ggwave.free(self.ggwave)

    def shutdown(self):
        """ alias so the listener service also releases the ggwave instance """
        self.default_shutdown()
