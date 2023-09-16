from distutils.spawn import find_executable
from os.path import isfile, expanduser

import pexpect
from ovos_plugin_manager.templates.transformers import AudioTransformer
from ovos_utils import create_daemon
from ovos_utils.log import LOG
from ovos_utils.messagebus import Message

from ovos_workshop.skills.ovos import OVOSSkill
from ovos_workshop.decorators import intent_handler


class GGWaveSkill(OVOSSkill):

    @intent_handler("ggwave.enable.intent")
    def handle_enable_ggwave(self, message):
        self.bus.emit(message.forward("ovos.ggwave.enable"))
        self.speak_dialog("ggwave.enabled")

    @intent_handler("ggwave.disable.intent")
    def handle_disable_ggwave(self, message):
        self.bus.emit(message.forward("ovos.ggwave.disable"))
        self.speak_dialog("ggwave.disabled")


# NOTE - could not get ggwave to work properly with the audio feed
# ran out of time so just used a subprocess
class GGWavePlugin(AudioTransformer):

    def __init__(self, config=None):
        config = config or {}
        super().__init__("ovos-audio-transformer-plugin-ggwave", 10, config)
        self.binpath = self.config.get("binary") or \
                       find_executable("ggwave-rx") or \
                       expanduser("~/.local/bin/ggwave-rx")
        if not isfile(self.binpath):
            raise ValueError(f"ggwave-rx not found in {self.binpath}, "
                             f"please install from https://github.com/ggerganov/ggwave")
        # TODO - individual config to enable/disable each
        self.OPCODES = {
            "SSID:": self.handle_wifi_ssid,
            "PSWD:": self.handle_wifi_pswd,
            "UTT:": self.handle_utt,
            "SPEAK:": self.handle_speak,
            "JSON:": self.handle_json,
            "BUS:": self.handle_bus,
            "GHS:": self.handle_skill,
            "PIP:": self.handle_pip
        }
        self._ssid = None
        self.vui = None
        # TODO - autoenable if wifi has not been setup previously
        self.user_enabled = False

    def bind(self, bus=None):
        """ attach messagebus """
        super().bind(bus)
        # we load the voice interface as part of this plugin
        # the skill interacts only via messagebus
        self.vui = GGWaveSkill(bus=self.bus, skill_id="ggwave.openvoiceos")
        self.bus.on("ovos.ggwave.enable", self.handle_enable)
        self.bus.on("ovos.ggwave.disable", self.handle_disable)

        self.daemon = create_daemon(self.monitor_thread)

    def handle_enable(self, message: Message):
        self.user_enabled = True

    def handle_disable(self, message: Message):
        self.user_enabled = False

    def shutdown(self):
        if self.vui is not None:
            self.vui.shutdown()

    def handle_skill(self, payload):
        if not payload.startswith("https://github.com/"):
            payload = f"https://github.com/{payload}"
        LOG.info(f"github skill to install: {payload}")
        self.bus.emit(Message("ovos.skills.install", {"url": payload}))

    def handle_pip(self, payload):
        LOG.info(f"pip package to install: {payload}")
        self.bus.emit(Message("ovos.pip.install", {"packages": []}))

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

    def handle_speak(self, payload):
        LOG.info(f"Speak: {payload}")
        self.bus.emit(Message("speak",  {"utterance": [payload]}))

    def handle_json(self, payload):
        LOG.info(f"JSON: {payload}")
        try:
            msg = Message.deserialize(payload)
            self.bus.emit(msg)
        except:
            LOG.exception("failed to deserialize message")

    def handle_wifi_pswd(self, payload):
        if not self._ssid:
            LOG.error("received wifi password but wifi SSID not set! ignoring")
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

    def monitor_thread(self):
        child = pexpect.spawn(self.binpath)
        marker = "Received sound data successfully: "
        while True:
            try:
                txt = child.readline().decode("utf-8").strip()
                if txt.startswith(marker):
                    payload = txt.split(marker)[-1][1:-1]
                    for opcode, handler in self.OPCODES.items():
                        if payload.startswith(opcode):
                            p = payload.split(opcode, 1)[-1]
                            handler(p)
                            break
                    else:
                        print(f"invalid ggwave payload: {payload}")
            except pexpect.exceptions.EOF:
                # exited
                print("Exited ggwave-rx process")
                break
            except pexpect.exceptions.TIMEOUT:
                # nothing happened for a while
                pass
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    from ovos_utils import wait_for_exit_signal

    binary = "/home/miro/PycharmProjects/ovos-audio-transformer-plugin-ggwave/ggwave/build/bin/ggwave-rx"

    gg = GGWavePlugin({"binary": binary})

    wait_for_exit_signal()