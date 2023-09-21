import datetime
import os
import stat
from distutils.spawn import find_executable
from os.path import isfile, expanduser
from platform import machine

import pexpect
import requests
from ovos_config import Configuration
from ovos_plugin_manager.templates.transformers import AudioTransformer
from ovos_utils import create_daemon
from ovos_utils.log import LOG
from ovos_utils.messagebus import Message
from ovos_workshop.app import OVOSAbstractApplication
from ovos_workshop.decorators import intent_handler


class GGWaveSkill(OVOSAbstractApplication):

    def initialize(self):
        self.add_event("ggwave.enabled", self.handle_ggwave_on)
        self.add_event("ggwave.disabled", self.handle_ggwave_off)
        self.enabled = False

    def handle_ggwave_on(self, message):
        self.enabled = True
        self.schedule_event(handler=self.handle_ggwave_off,
                            when=datetime.datetime.now() + datetime.timedelta(minutes=15),
                            name="ggwave.timeout")

    def handle_ggwave_off(self, message):
        self.enabled = False

    @intent_handler("enable.ggwave.intent")
    def handle_enable_ggwave(self, message):
        if not self.enabled:
            self.bus.emit(message.forward("ovos.ggwave.enable"))
            self.speak_dialog("ggwave.enabled")
        else:
            self.speak_dialog("ggwave.already.enabled")

    @intent_handler("disable.ggwave.intent")
    def handle_disable_ggwave(self, message):
        if self.enabled:
            self.bus.emit(message.forward("ovos.ggwave.disable"))
            self.cancel_scheduled_event("ggwave.timeout")
            self.speak_dialog("ggwave.disabled")
        else:
            self.speak_dialog("ggwave.already.disabled")


# NOTE - could not get ggwave to work properly with the audio feed
# ran out of time so just used a subprocess
class GGWavePlugin(AudioTransformer):

    def __init__(self, config=None):
        config = config or {}
        super().__init__("ovos-audio-transformer-plugin-ggwave", 10, config)
        self.binpath = expanduser(self.config.get("binary") or \
                                  find_executable("ggwave-rx") or \
                                  "~/.local/bin/ggwave-rx")
        if not isfile(self.binpath):
            self.download_ggwave()
        LOG.info(f"using binary: {self.binpath}")
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
        self.debug = self.config.get("debug", False)
        self._ssid = None
        self.vui = None
        self.user_enabled = self.config.get("start_enabled", False)

    def download_ggwave(self):
        arch = machine()
        if arch == 'x86_64':
            url = "https://artifacts.smartgic.io/artifacts/ggwave/ggwave-rx.x86_64"
        elif arch == "aarch64":
            url = "https://artifacts.smartgic.io/artifacts/ggwave/ggwave-rx.aarch64"
        else:
            LOG.error("ggwave-rx binary not available and pre-compiled binary unavailable for download")
            raise ValueError(f"ggwave-rx not found in {self.binpath}, "
                             f"please install from https://github.com/ggerganov/ggwave")
        LOG.info(f"downloading: {url}")
        with open(self.binpath, "wb") as f:
            f.write(requests.get(url).content)
        # make executable
        st = os.stat(self.binpath)
        os.chmod(self.binpath, st.st_mode | stat.S_IEXEC)

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

    def monitor_thread(self):
        child = pexpect.spawn(self.binpath)
        marker = "Received sound data successfully: "
        while True:
            try:
                txt = child.readline().decode("utf-8").strip()
                if txt and self.debug:
                    LOG.debug(txt)
                if txt.startswith(marker):

                    snd = Configuration().get("sounds", {}).get("ggwave_success", "snd/acknowledge.mp3")
                    if snd:
                        # no sound by default
                        self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))

                    payload = txt.split(marker)[-1][1:-1]

                    for opcode, handler in self.OPCODES.items():
                        if payload.startswith(opcode):
                            p = payload.split(opcode, 1)[-1]
                            if self.user_enabled:
                                handler(p)
                            else:
                                LOG.debug("ignoring ggwave payload, user did not enable ggwave")
                            break
                    else:
                        LOG.debug(f"invalid ggwave payload: {payload}")
                        snd = Configuration().get("sounds", {}).get("ggwave_error")
                        if snd:
                            # no sound by default
                            self.bus.emit(Message("mycroft.audio.play_sound", {"uri": snd}))
            except pexpect.exceptions.EOF:
                # exited
                LOG.error("Exited ggwave-rx process")
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
