import threading

import ggwave
import pyaudio  # TODO ditch me
from ovos_config import Configuration
from ovos_plugin_manager.templates.transformers import AudioTransformer
from ovos_utils import create_daemon
from ovos_utils.log import LOG, init_service_logger
from ovos_utils.messagebus import Message


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
        self.user_enabled = self.config.get("start_enabled", False)
        self.ggwave = ggwave.init()
        self._stop = threading.Event()

    def bind(self, bus=None):
        """ attach messagebus """
        super().bind(bus)
        # we load the voice interface as part of this plugin
        # the skill interacts only via messagebus
        self.bus.on("ovos.ggwave.enable", self.handle_enable)
        self.bus.on("ovos.ggwave.disable", self.handle_disable)
        self.daemon = create_daemon(self.monitor_thread)

    def handle_enable(self, message: Message):
        self.user_enabled = True
        self.bus.emit(message.forward("ovos.ggwave.enabled"))
        # TODO - dedicated sound
        self.bus.emit(Message("mycroft.audio.play_sound",
                              {"uri": "snd/acknowledge.mp3"}))

    def handle_disable(self, message: Message):
        self.user_enabled = False
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

    def on_audio(self, audio_data):
        """ Take any action you want, audio_data is a non-speech chunk
        """
        # TODO - remove thread and check ggwave audio here instead!
        # audio_data from listener is usually 16000 sample rate
        # not sure if ggwave requires 1024 chunk size?
        return audio_data

    def monitor_thread(self):
        p = pyaudio.PyAudio()

        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, input=True, frames_per_buffer=1024)

        try:
            while not self._stop.is_set():
                data = stream.read(1024, exception_on_overflow=False)
                res = ggwave.decode(self.ggwave, data)
                if (not res is None):
                    try:
                        payload = res.decode("utf-8")
                        snd = Configuration().get("sounds", {}).get("ggwave_success", "snd/acknowledge.mp3")
                        if snd:
                            # no sound by default
                            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

                        for opcode, handler in self.OPCODES.items():
                            if payload.startswith(opcode):
                                p = payload.split(opcode, 1)[-1]
                                if self.user_enabled:
                                    handler(p)
                                else:
                                    LOG.info("ignoring ggwave payload, user did not enable ggwave")
                                break
                        else:
                            LOG.debug(f"invalid ggwave payload: {payload}")
                            snd = Configuration().get("sounds", {}).get("ggwave_error")
                            if snd:
                                # no sound by default
                                self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))
                    except:
                        pass
        except KeyboardInterrupt:
            pass

        stream.stop_stream()
        stream.close()
        p.terminate()

    def default_shutdown(self):
        """ perform any shutdown actions """
        self._stop.set()
        ggwave.free(self.ggwave)


def launch_cli():
    from ovos_utils import wait_for_exit_signal
    from ovos_bus_client.util import get_mycroft_bus
    init_service_logger("ggwave")

    gg = GGWavePlugin({"start_enabled": True})

    bus = get_mycroft_bus()
    gg.bind(bus)

    wait_for_exit_signal()  # wait for CTRl+C


if __name__ == "__main__":
    launch_cli()
